"""Use-case generator (narrow behavior vocabulary, CQRS application service).

A ``use_case`` is the application-layer behavior home: a frozen intent
message, a result, and an explicit handler that

* loads its aggregate through an injected repository,
* guards a state transition against the persisted value when authored,
* applies authored writes — ``input.<name>``, the acting principal's
  subject, and the invocation time all arrive **on the message** (callers
  inject them), so the handler body stays deterministic and testable,
* persists the aggregate,
* optionally appends result events to an injected event store after the save,
* and optionally invokes injected follow-up job runners.

These standalone effects are not atomic with the aggregate update. An event
store is not necessarily an outbox, and absent optional job runners are skipped;
application composition must supply and verify its own delivery guarantees.
The explicit ``inbox_notification``/``atomic_transition`` combination instead
uses the native same-provider transaction; it requires a trusted channel binding.

The vocabulary is deliberately narrow. Authors can describe additional
application-owned work as custom steps; those produce ``@INTENT``/``@TODO``
markers and fail before persistence until implemented. Input references are
checked before rendering; callers still validate aggregate constraints,
connections and delivery guarantees rather than silently ignoring them.
"""

from __future__ import annotations

from keyword import iskeyword
import math
from pathlib import Path
from typing import Any

from quadkit.codegen import (
    FieldSpec,
    GenerationResult,
    GeneratorBase,
    annotation_for,
    import_lines,
    parse_fields,
)
from quadkit.contracts.cli.generators import resolve_options
from quadkit.events.cli.generators.use_case_counters import compile_counters
from quadkit.events.cli.generators.use_case_inbox import compile_inbox_notification
from quadkit.events.cli.generators.use_case_outputs import compile_output_fields
from quadkit.events.cli.generators.use_case_related_reads import compile_related_reads
from quadkit.events.cli.generators.use_case_related_values import (
    compile_related_write_checks,
)
from quadkit.serialization import loads_str


class UseCaseGenerator(GeneratorBase):
    """Generate a use-case module (message + result + handler).

    Behavior arrives through the ``spec`` keyword: a dict describing the
    compiled use case —

    ``transition``
        ``{"field", "from", "to"}`` — the aggregate-state guard applied in
        ``handle()`` second (after the aggregate exists).
    ``validate_inputs``
        Validate basic command field types and requiredness in the handler,
        before repository access. This is opt-in; it does not enforce field
        formats or domain/aggregate constraints and does not coerce values.
    ``strict_json_inputs``
        Require JSON object inputs to contain serializable JSON values with
        string keys at every level, finite numbers and valid Unicode. Cycles
        and values beyond the serializer's depth/number limits are rejected.
        Requires basic input validation; standalone output is unchanged by default.
    ``storage_text_inputs``
        Names of validated string inputs written to SQL text. Rejects NUL and
        unpaired surrogates before reads. Supports injected principal_sub.
    ``storage_json_inputs``
        Names of strict JSON object inputs written to SQL JSON columns. Rejects
        NUL in nested string values and keys; requires strict JSON validation.
    ``storage_temporal_inputs``
        Map SQL-written date/datetime/time input names (including an injected
        clock) to their types. Dates exclude Python's endpoints, datetimes
        require offsets and must normalize strictly inside the UTC endpoints,
        and times cannot have tzinfo. These checks require built-in temporal
        types, not subclasses. Requires basic validation. With typed
        outcomes an invalid injected clock returns invalid_context, not
        invalid_input; storage may normalize datetime offsets.
    ``length_inputs``
        Optional mapping of text/bytes input names to inclusive non-negative
        length bounds. With principal_required, principal_sub can be bounded
        as well. Requires basic input validation; no coercion is done.
    ``alphabet_inputs``
        Optional mapping of string inputs to their permitted ASCII characters.
        Requires basic validation; use length_inputs for any length limits.
    ``numeric_inputs``
        Optional mapping of numeric input names to inclusive ``min``/``max``
        bounds. Requires basic validation; float inputs must also be finite.
    ``enum_inputs``
        Optional mapping of input names to allowed strings. Requires basic
        input validation; the handler rejects values outside the supplied
        options before accessing its repository.
    ``uuid_write_fields``
        Optional target names backed by SQL string UUID columns. When enabled,
        validated UUID inputs are converted to strings only at persistence;
        nullable values remain null. Standalone output leaves values unchanged.
    ``atomic_transition``
        When true, require a repository with ``get_for_transition`` and
        ``transition_if``: the latter compares the persisted state in the
        update statement and returns a Result containing the literal ``True``
        only after a successful write. An error or any other success value fails
        the operation. Ordinary standalone CLI output defaults to false.
        This does not make authorization or external effects atomic.
    ``writes``
        ``[{"field", "source"}]`` — aggregates assigned after the guard:
        ``input.<name>`` names an ASCII Python identifier declared in
        ``fields_str``, never an expression or arbitrary message attribute.
        The same rule applies to stage/enqueue payload sources, including
        dry runs. ``principal`` and ``clock`` name injected invocation
        context, not authored inputs. A ``principal`` source requires
        ``principal_required`` in writes and both effect payload lanes.
    ``output_fields``
        Optional closed projections {name, type, source, required}. Types are
        str/int/float/bool/uuid/date/datetime/time/json; sources name declared inputs or aggregate fields.
        UUID outputs are canonical strings (typed UUID sources are normalized;
        storage strings must already be canonical). Date outputs use YYYY-MM-DD
        from exact dates or canonical strings, never datetime coercion.
        Aware datetime outputs normalize to UTC RFC3339; naive values fail.
        Local time outputs reject tzinfo and fold ambiguity; no offset is inferred.
        Output-bound datetime/time inputs normalize once before repository access.
        JSON-object outputs validate native JSON trees and clone detached snapshots.
        Output-bound JSON inputs fail before reads, even without SQL assignment.
        Nullable keys remain present.
        All projections are validated and JSON-checked before persistence.
        The caller still validates external aggregate shape and disclosure policy.
    ``related_reads``
        Optional list of {name, key, fields}: read-only related snapshots from
        explicit injected ``related_<name>_repository`` dependencies. Keys must
        name required string/UUID inputs and require ``validate_inputs``.
        Writes may copy only allowlisted ``related.<name>.<field>`` values.
        No chained reads, related mutations, automatic authorization or shared
        transaction is implied. Effects/outputs do not accept these sources.
    ``related_write_checks``
        Optional explicit scalar target checks for every related write. Each
        record names field, type (str/int/float/bool), nullable and optional
        min_length/max_length, minimum/maximum or string enum. Requires
        validate_inputs. Invalid values fail before any aggregate mutation.
        Absent metadata retains legacy unchecked standalone behavior.
    ``counters``
        Optional list of {field, delta, minimum, maximum} bounded integer updates.
        Requires an explicit atomic string transition and a repository declaring
        supports_transition_expected_values_v1 as literal True. Every old/new
        counter is validated before mutation; all snapshots are passed to the
        same conditional write. No retry, related lookup or effect atomicity.
    ``inbox_notification``
        Explicit {title, body_field} opt-in. Requires principal_required,
        validate_inputs, typed_outcomes and atomic_transition. The body field
        must be written from a required string input in this same transition.
        The host injects a native InboxDeliveryChannel (no request-selected
        recipient). The repository must advertise supports_transition_inbox_v1
        and implement transition_inbox_if with the conditional update and
        native SQL queue insert in one transaction, returning its delivery ID.
        Result data reports notification=queued, never sent. A separate native
        worker delivers it. Other effects/custom work/counters/related reads
        are refused. This is not HTTP authentication or automatic host wiring.
    ``stages``
        ``[{"event", "import", "payload": {<event field>: <source>}}]`` —
        events appended to an injected event store after the save; the store
        must actually support an outbox to provide outbox behavior.
    ``enqueues``
        ``[{"task_class", "import", "payload": {<ctor arg>: <source>}}]`` —
        optional injected runners invoked after the save; absent runners skip
        their jobs. Neither effect is atomic with the aggregate write.
    ``guard``
        Require an injected policy and evaluate it against the trusted
        principal and loaded aggregate before applying any changes.
    ``repository`` / ``repository_import``
        Aggregate repository protocol the handler is constructed with.
    ``principal_required``
        Adds ``principal_sub`` and ``principal`` to the message. Callers
        must authenticate the principal before dispatch; the handler checks
        that its subject matches and fails closed if it is missing.
    ``typed_outcomes``
        Opt in to stable result codes for invalid input, policy denial,
        missing aggregates, repository errors, transition rejection and failed
        writes, so adapters need not infer outcomes from messages. Only an
        actual NotFoundError is classified as missing.
    ``package``
        Import roots the writer resolved (event/task/policy modules differ
        per project layout, so the writer spells the imports).

    Absent entries emit a working base handler (the same shape
    ``quadkit gen command`` produces) so plain CLI use stays meaningful.
    """

    # The Playground requires this opt-in before passing its builder spec:
    # validate_inputs, enum_inputs, length_inputs, numeric_inputs,
    # typed_outcomes, uuid_write_fields, atomic_transition and fail-closed custom_steps must not
    # be silently ignored by an older generator with a compatible signature.
    # Changes that weaken these behaviors require a new capability version.
    supports_builder_use_case_v2 = True
    # v3 additionally promises strict recursive JSON input validation.
    supports_builder_use_case_v3 = True
    # v4 distinguishes missing aggregates from other repository failures.
    supports_builder_use_case_v4 = True
    # v5 guarantees length_inputs also validate the injected principal_sub.
    supports_builder_use_case_v5 = True
    # v6 additionally validates SQL-written text and injected subjects.
    supports_builder_use_case_v6 = True
    # v7 adds SQL JSON string/key portability checks.
    supports_builder_use_case_v7 = True
    # v8 adds opt-in validated ASCII alphabet input checks.
    supports_builder_use_case_v8 = True
    # v9 validates opt-in SQL temporal values before repository access and
    # distinguishes an invalid injected clock from a client input error.
    supports_builder_use_case_v9 = True
    # v10 requires a literal True acknowledgement of conditional writes.
    supports_builder_use_case_v10 = True
    supports_builder_use_case_v11 = True
    # v12 adds explicit bounded counters with required integer-CAS capability.
    supports_builder_use_case_v12 = True
    # v13 validates UUID projections and emits canonical JSON strings before writes.
    supports_builder_use_case_v13 = True
    # v14 adds canonical date outputs, excluding datetime and arbitrary coercion.
    supports_builder_use_case_v14 = True
    # v15 normalizes aware datetime outputs to UTC; output-bound inputs fail before reads.
    supports_builder_use_case_v15 = True
    # v16 adds offset-free local time projections and pre-read input checks.
    supports_builder_use_case_v16 = True
    # v17 adds detached native JSON-object output snapshots.
    supports_builder_use_case_v17 = True
    # Standalone opt-in scalar checks for every authored related write.
    # Callers must check this capability rather than trust a version string.
    supports_related_write_checks_v1 = True
    # Explicit prepared inbox envelope and capability-checked transactional enqueue.
    supports_atomic_inbox_v1 = True
    # A required enqueue (``enqueues[].required``) fails closed: an unbound
    # runner returns a failure rather than silently skipping the effect, a
    # queue rejection is translated into a returned partial-failure outcome
    # (the aggregate write is already committed), and a payload key outside the
    # declared ``enqueues[].params`` is refused at parse time.
    supports_use_case_job_effect_v1 = True
    name = "use_case"
    description = "Generate a use case (intent message + result + handler)"
    default_output_dir = "src/usecases"

    def __init__(self, output_dir: str | Path = "src/usecases") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        spec: dict[str, Any] | str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a use-case handler module.

        Args:
            name: Use-case name, e.g. ``"PublishPost"`` or ``"publish_post"``.
            fields_str: Optional ``name:type`` input list in parser syntax.
            spec: Compiled behavior spec (see the class docstring); a JSON
                string is accepted for CLI use.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        if isinstance(spec, str):
            spec = loads_str(spec) if spec.strip() else None
        spec = dict(spec or {})

        fields: list[FieldSpec] = parse_fields(fields_str) if fields_str else []
        inbox_notification = compile_inbox_notification(spec, fields)
        output_fields = compile_output_fields(spec.get("output_fields"), fields)
        related_reads = compile_related_reads(spec, fields)
        related_write_checks = compile_related_write_checks(spec, related_reads)
        related_fields = {read.name: frozenset(read.fields) for read in related_reads}
        # Capture authored inputs before adding trusted invocation context.
        # Every source-bearing lane uses the same vocabulary boundary.
        input_names = frozenset(field.name for field in fields)

        # Effect-adjacent context crosses the boundary as message fields:
        # adapters inject the acting principal subject and the invocation
        # time onto the command, keeping the handler pure.
        principal_required = bool(spec.get("principal_required"))
        if self._uses_source(spec, "principal") and not principal_required:
            raise ValueError("use_case principal source requires principal_required")
        if spec.get("guard") and not principal_required:
            raise ValueError("a guarded use case requires an authenticated principal")
        if principal_required and "principal_sub" not in {f.name for f in fields}:
            fields.append(FieldSpec(name="principal_sub", type="str"))
        if self._uses_source(spec, "clock") and "occurred_at" not in {
            f.name for f in fields
        }:
            fields.append(FieldSpec(name="occurred_at", type="datetime"))

        validate_inputs = bool(spec.get("validate_inputs"))
        input_checks = []
        if validate_inputs:
            runtime_types = {
                "str": "str",
                "int": "int",
                "float": "float",
                "bool": "bool",
                "datetime": "datetime",
                "date": "date",
                "time": "time",
                "UUID": "UUID",
                "dict[str, Any]": "dict",
                "bytes": "bytes",
            }
            for field in fields:
                annotation = annotation_for(field.type)
                runtime_type = runtime_types.get(annotation)
                if runtime_type is None:
                    raise ValueError(
                        f"use_case input type {field.type!r} cannot be validated"
                    )
                input_checks.append(
                    {
                        "name": field.name,
                        "type": runtime_type,
                        "required": field.required,
                    }
                )

        strict_json_inputs = bool(spec.get("strict_json_inputs"))
        if strict_json_inputs and not validate_inputs:
            raise ValueError("use_case strict_json_inputs requires validate_inputs")
        output_json_inputs: dict[str, bool] = {}
        for slot in output_fields:
            if slot["json"] and slot["input"]:
                input_name = slot["input"]
                output_json_inputs[input_name] = slot[
                    "required"
                ] or output_json_inputs.get(input_name, False)
        json_checks = [
            check
            for check in input_checks
            if strict_json_inputs
            and check["type"] == "dict"
            and check["name"] not in output_json_inputs
        ]

        field_map = {field.name: field for field in fields}
        raw_temporal = spec.get("storage_temporal_inputs")
        if raw_temporal is None:
            raw_temporal = {}
        if not isinstance(raw_temporal, dict):
            raise TypeError("use_case storage_temporal_inputs must be a mapping")
        if raw_temporal and not validate_inputs:
            raise ValueError(
                "use_case storage_temporal_inputs requires validate_inputs"
            )
        temporal_checks = []
        for field_name, kind in raw_temporal.items():
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or iskeyword(field_name)
                or field_name not in field_map
                or kind not in ("date", "datetime", "time")
                or annotation_for(field_map[field_name].type) != kind
            ):
                raise ValueError(
                    "use_case storage_temporal_inputs must name matching temporal fields"
                )
            temporal_checks.append({"name": field_name, "type": kind})
        temporal_checks.sort(key=lambda check: check["name"])
        has_temporal_clock = raw_temporal.get(
            "occurred_at"
        ) == "datetime" and self._uses_source(spec, "clock")
        for check in input_checks:
            check["temporal_clock"] = (
                has_temporal_clock and check["name"] == "occurred_at"
            )
        for check in temporal_checks:
            check["temporal_clock"] = (
                has_temporal_clock and check["name"] == "occurred_at"
            )

        raw_enums = spec.get("enum_inputs")
        if raw_enums is None:
            raw_enums = {}
        if not isinstance(raw_enums, dict):
            raise TypeError("use_case enum_inputs must be a mapping")
        enum_checks: list[dict[str, str]] = []
        raw_storage_json = spec.get("storage_json_inputs")
        if raw_storage_json is None:
            raw_storage_json = ()
        if not isinstance(raw_storage_json, (list, tuple)):
            raise TypeError("use_case storage_json_inputs must be a list")
        if raw_storage_json and not strict_json_inputs:
            raise ValueError("use_case storage_json_inputs requires strict_json_inputs")
        if any(
            not isinstance(name, str)
            or name not in field_map
            or not name.isidentifier()
            or iskeyword(name)
            or annotation_for(field_map[name].type) != "dict[str, Any]"
            for name in raw_storage_json
        ):
            raise ValueError("use_case storage_json_inputs must name JSON fields")
        storage_json_checks = frozenset(raw_storage_json)
        for check in json_checks:
            check["storage_text"] = check["name"] in storage_json_checks

        raw_storage_text = spec.get("storage_text_inputs")
        if raw_storage_text is None:
            raw_storage_text = ()
        if not isinstance(raw_storage_text, (list, tuple)):
            raise TypeError("use_case storage_text_inputs must be a list")
        if raw_storage_text and not validate_inputs:
            raise ValueError("use_case storage_text_inputs requires validate_inputs")
        if any(
            not isinstance(name, str)
            or name not in field_map
            or not name.isidentifier()
            or iskeyword(name)
            or annotation_for(field_map[name].type) != "str"
            for name in raw_storage_text
        ):
            raise ValueError("use_case storage_text_inputs must name string fields")
        text_checks = sorted(set(raw_storage_text))
        if raw_enums and not validate_inputs:
            raise ValueError("use_case enum_inputs requires validate_inputs")
        for field_name, values in raw_enums.items():
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or iskeyword(field_name)
                or field_name not in field_map
                or annotation_for(field_map[field_name].type) != "str"
            ):
                raise ValueError(
                    f"use_case enum input {field_name!r} must name a string field"
                )
            if (
                not isinstance(values, (tuple, list))
                or not values
                or any(not isinstance(value, str) for value in values)
            ):
                raise ValueError(
                    f"use_case enum input {field_name!r} needs string options"
                )
            enum_checks.append(
                {"name": field_name, "values_literal": repr(tuple(values))}
            )
        enum_checks.sort(key=lambda check: check["name"])

        raw_alphabets = spec.get("alphabet_inputs")
        if raw_alphabets is None:
            raw_alphabets = {}
        if not isinstance(raw_alphabets, dict):
            raise TypeError("use_case alphabet_inputs must be a mapping")
        if raw_alphabets and not validate_inputs:
            raise ValueError("use_case alphabet_inputs requires validate_inputs")
        alphabet_checks: list[dict[str, str]] = []
        for field_name, alphabet in raw_alphabets.items():
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or iskeyword(field_name)
                or field_name not in field_map
                or annotation_for(field_map[field_name].type) != "str"
            ):
                raise ValueError("use_case alphabet input must name a string field")
            if (
                not isinstance(alphabet, str)
                or not alphabet
                or len(alphabet) > 64
                or len(set(alphabet)) != len(alphabet)
                or any(
                    not (char.isascii() and (char.isalnum() or char in "_-"))
                    for char in alphabet
                )
            ):
                raise ValueError(
                    "use_case alphabet input needs unique ASCII letters, digits, underscore or hyphen"
                )
            alphabet_checks.append(
                {"name": field_name, "alphabet_literal": repr(alphabet)}
            )
        alphabet_checks.sort(key=lambda check: check["name"])

        raw_lengths = spec.get("length_inputs")
        if raw_lengths is None:
            raw_lengths = {}
        if not isinstance(raw_lengths, dict):
            raise TypeError("use_case length_inputs must be a mapping")
        if raw_lengths and not validate_inputs:
            raise ValueError("use_case length_inputs requires validate_inputs")
        length_checks: list[dict[str, Any]] = []
        for field_name, bounds in raw_lengths.items():
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or iskeyword(field_name)
                or field_name not in field_map
                or annotation_for(field_map[field_name].type) not in {"str", "bytes"}
            ):
                raise ValueError(
                    f"use_case length input {field_name!r} must name a text or bytes field"
                )
            if not isinstance(bounds, dict) or set(bounds) - {"min", "max"}:
                raise ValueError(
                    f"use_case length input {field_name!r} needs min/max bounds"
                )
            low, high = bounds.get("min"), bounds.get("max")
            for bound in (low, high):
                if bound is not None and (
                    isinstance(bound, bool) or not isinstance(bound, int) or bound < 0
                ):
                    raise ValueError(
                        f"use_case length input {field_name!r} needs non-negative integer bounds"
                    )
            if low is None and high is None:
                raise ValueError(f"use_case length input {field_name!r} needs a bound")
            if low is not None and high is not None and low > high:
                raise ValueError(
                    f"use_case length input {field_name!r} has no allowed length"
                )
            if principal_required and field_name == "principal_sub" and high == 0:
                raise ValueError(
                    "use_case principal_sub length has no non-empty subject"
                )
            length_checks.append({"name": field_name, "min": low, "max": high})
        length_checks.sort(key=lambda check: check["name"])

        raw_ranges = spec.get("numeric_inputs")
        if raw_ranges is None:
            raw_ranges = {}
        if not isinstance(raw_ranges, dict):
            raise TypeError("use_case numeric_inputs must be a mapping")
        if raw_ranges and not validate_inputs:
            raise ValueError("use_case numeric_inputs requires validate_inputs")
        numeric_checks: list[dict[str, Any]] = []
        for field_name, bounds in raw_ranges.items():
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or iskeyword(field_name)
                or field_name not in field_map
                or annotation_for(field_map[field_name].type) not in {"int", "float"}
            ):
                raise ValueError(
                    f"use_case numeric input {field_name!r} must name a numeric field"
                )
            if not isinstance(bounds, dict) or set(bounds) - {"min", "max"}:
                raise ValueError(
                    f"use_case numeric input {field_name!r} needs min/max bounds"
                )
            low, high = bounds.get("min"), bounds.get("max")
            for bound in (low, high):
                if bound is not None and not _finite_number(bound):
                    raise ValueError(
                        f"use_case numeric input {field_name!r} needs finite bounds"
                    )
            if low is None and high is None:
                raise ValueError(f"use_case numeric input {field_name!r} needs a bound")
            if (
                low is not None
                and high is not None
                and (
                    low > high
                    or (
                        annotation_for(field_map[field_name].type) == "int"
                        and math.ceil(low) > math.floor(high)
                    )
                )
            ):
                raise ValueError(
                    f"use_case numeric input {field_name!r} has no allowed value"
                )
            numeric_checks.append(
                {
                    "name": field_name,
                    "min_literal": repr(low) if low is not None else None,
                    "max_literal": repr(high) if high is not None else None,
                }
            )
        numeric_checks.sort(key=lambda check: check["name"])

        writes = self._write_context(spec.get("writes"), input_names, related_fields)
        uuid_targets = spec.get("uuid_write_fields")
        if uuid_targets is None:
            uuid_targets = ()
        if not isinstance(uuid_targets, (tuple, list, set, frozenset)) or any(
            not isinstance(target, str) for target in uuid_targets
        ):
            raise TypeError("use_case uuid_write_fields must be a collection of names")
        if len(set(uuid_targets)) != len(uuid_targets):
            raise ValueError("use_case uuid_write_fields cannot contain duplicates")
        if uuid_targets and not validate_inputs:
            raise ValueError("use_case uuid_write_fields requires validate_inputs")
        for target in uuid_targets:
            matching = [write for write in writes if write["field"] == target]
            if len(matching) != 1:
                raise ValueError("uuid storage target must name exactly one write")
            source = matching[0]["source"]
            input_field = field_map.get(source.removeprefix("input."))
            if (
                not source.startswith("input.")
                or input_field is None
                or annotation_for(input_field.type) != "UUID"
            ):
                raise ValueError("uuid storage target requires a UUID input source")
        for write in writes:
            write["uuid_string"] = write["field"] in uuid_targets

        use_case_name = self._to_pascal_case(name)
        use_case_snake = self._to_snake_case(name)

        extra_imports = sorted(
            {str(line) for key in ("repository_import",) if (line := spec.get(key))}
            | {
                str(stage.get("import"))
                for stage in spec.get("stages") or ()
                if stage.get("import")
            }
            | {
                str(enqueue.get("import"))
                for enqueue in spec.get("enqueues") or ()
                if enqueue.get("import")
            }
        )
        if any(enqueue.get("required") for enqueue in spec.get("enqueues") or ()):
            extra_imports = sorted(
                {
                    *extra_imports,
                    "from quadkit.contracts.infra.tasks.exceptions import TaskQueueError",
                }
            )

        # Standalone use needs a resolvable repository contract; builder
        # emission supplies its own concrete repository and import instead.
        repository = spec.get("repository") or "RepositoryProtocol"
        local_repository_protocol = repository == "RepositoryProtocol" and not spec.get(
            "repository_import"
        )
        atomic_transition = bool(
            spec.get("atomic_transition") and spec.get("transition")
        )
        # Date validation rejects datetime (a date subclass), so that runtime
        # check needs datetime even when it is not a declared field type.
        needs_datetime_check = any(check["type"] == "date" for check in input_checks)
        uses_aggregate = (
            bool(output_fields)
            or bool(spec.get("guard") or spec.get("transition") or writes)
            or any(
                str(source).startswith("aggregate.")
                for effect in (
                    *(spec.get("stages") or ()),
                    *(spec.get("enqueues") or ()),
                )
                for source in (effect.get("payload") or {}).values()
            )
        )

        projected_output_inputs: dict[tuple[str, str], bool] = {}
        for slot in output_fields:
            kind = (
                "datetime"
                if slot["datetime"]
                else "time"
                if slot["time"]
                else "json"
                if slot["json"]
                else None
            )
            if kind and slot["input"]:
                source_name = slot["input"]
                key = (kind, source_name)
                projected_output_inputs[key] = slot[
                    "required"
                ] or projected_output_inputs.get(key, False)
                slot["expression"] = f"_output_{kind}_{source_name}"

        context: dict[str, Any] = {
            "use_case_name": use_case_name,
            "use_case_snake": use_case_snake,
            "fields": [
                {
                    "name": field.name,
                    "type": annotation_for(field.type),
                    "required": field.required,
                }
                for field in fields
            ],
            "imports": import_lines(
                (field.type for field in fields),
                always=[
                    "Any",
                    "UUID",
                    *(
                        ["datetime"]
                        if needs_datetime_check
                        or any(slot["datetime"] for slot in output_fields)
                        else []
                    ),
                    *(["date"] if any(slot["date"] for slot in output_fields) else []),
                    *(["time"] if any(slot["time"] for slot in output_fields) else []),
                ],
            ),
            "extra_imports": extra_imports,
            "repository": repository,
            "local_repository_protocol": local_repository_protocol,
            "uses_aggregate": uses_aggregate,
            "has_occurred_at": any(field.name == "occurred_at" for field in fields),
            "principal_required": principal_required,
            "validate_inputs": validate_inputs,
            "input_checks": input_checks,
            "json_checks": json_checks,
            "output_fields": output_fields,
            "has_uuid_outputs": any(slot["uuid"] for slot in output_fields),
            "has_date_outputs": any(slot["date"] for slot in output_fields),
            "has_datetime_outputs": any(slot["datetime"] for slot in output_fields),
            "has_time_outputs": any(slot["time"] for slot in output_fields),
            "has_json_outputs": any(slot["json"] for slot in output_fields),
            "projected_output_inputs": [
                {
                    "kind": kind,
                    "name": name,
                    "required": required,
                    "storage_text": name in storage_json_checks,
                }
                for (kind, name), required in projected_output_inputs.items()
            ],
            "text_checks": text_checks,
            "temporal_checks": temporal_checks,
            "needs_sql_datetime": any(
                check["type"] == "datetime" for check in temporal_checks
            ),
            "enum_checks": enum_checks,
            "alphabet_checks": alphabet_checks,
            "length_checks": length_checks,
            "numeric_checks": numeric_checks,
            "needs_math": bool(related_write_checks)
            or any(check["type"] == "float" for check in input_checks),
            "guard": bool(spec.get("guard")),
            "inbox_notification": inbox_notification,
            "typed_outcomes": bool(spec.get("typed_outcomes")),
            "atomic_transition": atomic_transition,
            "transition": self._transition_context(spec.get("transition")),
            "writes": writes,
            "related_reads": related_reads,
            "related_write_checks": related_write_checks,
            "counters": compile_counters(spec),
            # Comments must stay single-line even for direct CLI callers.
            "custom_steps": [
                " ".join(step.split())
                for step in spec.get("custom_steps") or ()
                if isinstance(step, str) and step.strip()
            ],
            "stages": [
                {
                    "event": stage.get("event"),
                    "payload": [
                        {
                            "field": field_name,
                            "expression": self._expression(source, input_names),
                        }
                        for field_name, source in sorted(
                            (stage.get("payload") or {}).items()
                        )
                    ],
                }
                for stage in spec.get("stages") or ()
            ],
            "enqueues": [
                self._enqueue_context(enqueue, input_names)
                for enqueue in spec.get("enqueues") or ()
            ],
        }
        content = self.render_template("use_case.py.jinja2", context)
        file_path = self.output_dir / f"{use_case_snake}_use_case.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _uses_source(spec: dict[str, Any], token: str) -> bool:
        for write in spec.get("writes") or ():
            if write.get("source") == token:
                return True
        for effect in (*(spec.get("stages") or ()), *(spec.get("enqueues") or ())):
            for source in (effect.get("payload") or {}).values():
                if source == token:
                    return True
        return False

    def _enqueue_context(
        self, enqueue: dict[str, Any], input_names: frozenset[str]
    ) -> dict[str, Any]:
        """Compile one enqueue, closing a required effect.

        A ``required`` enqueue must name its runner — the generated handler
        fails closed when the binding is absent rather than skipping the
        effect. When ``params`` is declared, only those parameters may be
        mapped; an undeclared key is refused at parse time instead of reaching
        the runner as an opaque keyword argument.
        """
        runner_class = enqueue.get("runner_class")
        required = bool(enqueue.get("required"))
        if required and not runner_class:
            raise ValueError(
                "use_case spec: a required enqueue must declare runner_class"
            )
        payload = enqueue.get("payload") or {}
        params = enqueue.get("params")
        if params is not None:
            unknown = sorted(set(payload) - set(params))
            if unknown:
                raise ValueError(
                    "use_case spec: enqueue payload field(s) "
                    f"{unknown!r} are not in the declared params"
                )
        return {
            "task_class": enqueue.get("task_class"),
            "runner_class": runner_class,
            "runner_attr": self._to_snake_case(str(runner_class or "task_runner")),
            "required": required,
            "payload": [
                {
                    "field": field_name,
                    "expression": self._expression(source, input_names),
                }
                for field_name, source in sorted(payload.items())
            ],
        }

    @staticmethod
    def _transition_context(raw: Any) -> dict[str, Any] | None:
        if isinstance(raw, dict) and raw.get("field"):
            return {
                "field": raw.get("field"),
                "from": raw.get("from"),
                "from_literal": _literal(raw.get("from")),
                "to": raw.get("to"),
                "to_literal": _literal(raw.get("to")),
            }
        return None

    @staticmethod
    def _expression(
        source: Any,
        input_names: frozenset[str],
        related_fields: dict[str, frozenset[str]] | None = None,
    ) -> str:
        """Resolve data references without accepting executable input suffixes."""
        token = str(source or "")
        if token.startswith("input."):
            name = token[6:]
            if (
                not name.isascii()
                or not name.isidentifier()
                or iskeyword(name)
                or name not in input_names
            ):
                raise ValueError(
                    f"use_case spec: input source {source!r} must name a declared input"
                )
            return f"command.{name}"
        if token.startswith("related."):
            parts = token.split(".")
            if (
                len(parts) != 3
                or related_fields is None
                or parts[1] not in related_fields
                or parts[2] not in related_fields[parts[1]]
            ):
                raise ValueError(
                    "related source must name an allowlisted read field in a write"
                )
            return f"related_rows[{parts[1]!r}][{parts[2]!r}]"
        if token == "principal":
            return "command.principal_sub"
        if token == "clock":
            return "command.occurred_at"
        if token.startswith("aggregate."):
            return f"aggregate[{token[10:]!r}]"
        # The writer validates the vocabulary; an unknown token fails loudly
        # at parse time, never silently.
        raise ValueError(f"use_case spec: unknown source {source!r}")

    def _write_context(
        self,
        raw: Any,
        input_names: frozenset[str],
        related_fields: dict[str, frozenset[str]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "field": write.get("field"),
                "source": str(write.get("source", "")),
                "expression": self._expression(
                    write.get("source"), input_names, related_fields
                ),
            }
            for write in raw or ()
        ]


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _literal(value: Any) -> str:
    """Render a transition endpoint as a Python literal (strings quoted)."""
    if isinstance(value, str):
        return repr(value)
    return repr(value)


__all__ = ["UseCaseGenerator"]
