from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from quadkit.web.cli.generators.controller import ControllerGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _render(tmp_path: Path, *layout: str, **kwargs: object) -> str:
    """Generate a controller inside an anchored src-layout project.

    Args:
        tmp_path: Scratch project root.
        *layout: Output directory parts below the project root.
        **kwargs: Forwarded to :meth:`ControllerGenerator.generate`.

    Returns:
        The rendered controller source.
    """
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path.joinpath(*layout)
    out.mkdir(parents=True, exist_ok=True)
    result = ControllerGenerator(output_dir=out).generate("Message", **kwargs)
    return Path(result.files_created[0]).read_text()


def test_controller_uses_resource_path():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        result = gen.generate("Message", path="/api/messages")
        file_path = result.files_created[0]
        content = Path(file_path).read_text()
        assert (
            '@get("/api/messages", response_schema_model=CrudCollectionResponse[Message], responses=ValidationErrorFilter.default_documented_responses(), result_errors=[NotFoundError])'
            in content
        )
        assert (
            '@get("/api/messages/{item_id}", response_schema_model=Message, result_errors=[NotFoundError])'
            in content
        )
        assert (
            '@post("/api/messages", status_code=201, request_model=MessageCreate, response_schema_model=Message, result_errors=[InvalidMessageError, ConflictError, DomainValidationError, NotFoundError])'
            in content
        )
        assert (
            '@put("/api/messages/{item_id}", request_model=MessageUpdate, response_schema_model=Message, result_errors=[InvalidMessageError, ConflictError, DomainValidationError, NotFoundError])'
            in content
        )
        assert (
            '@delete("/api/messages/{item_id}", response_schema_model=CrudDeleteResponse, result_errors=[ConflictError, NotFoundError])'
            in content
        )


def test_controller_default_path_uses_the_contracts_plural() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = ControllerGenerator(output_dir=tmp).generate("SavedSearch")
        content = Path(result.files_created[0]).read_text()

        assert (
            '@get("/saved_searches", response_schema_model=CrudCollectionResponse[SavedSearch], responses=ValidationErrorFilter.default_documented_responses(), result_errors=[NotFoundError])'
            in content
        )
        assert "/saved_searchs" not in content


def test_controller_delegates_to_repo():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        gen.generate("Message")
        content = Path(tmp, "message_controller.py").read_text()
        assert "self.repo.list(" in content
        assert "self.repo.get(" in content
        assert "self.repo.create(" in content
        assert "self.repo.update(" in content
        assert "self.repo.delete(" in content


def test_controller_no_double_suffix():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        result = gen.generate("MessageController")
        file_path = result.files_created[0]
        assert not str(file_path).endswith("_controller_controller.py")
        content = Path(file_path).read_text()
        assert "class MessageController(Controller)" in content
        assert "Service" not in content


# -- QK-1: sibling package imports follow the project structure ----------


def test_repository_import_is_bare_in_structured_layout(tmp_path: Path) -> None:
    """Structured layouts keep component packages directly under ``src``."""
    content = _render(tmp_path, "src", "controllers")
    assert "from repositories.message_repository import MessageRepository" in content
    assert (
        "from domains.message import Message, MessageCreate, MessageUpdate" in content
    )


def test_repository_import_is_prefixed_in_minimal_layout(tmp_path: Path) -> None:
    """Minimal layouts nest component packages under the app package."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert (
        "from app.repositories.message_repository import MessageRepository" in content
    )
    assert (
        "from app.domains.message import Message, MessageCreate, MessageUpdate"
        in content
    )


def test_repository_import_is_prefixed_in_modular_layout(tmp_path: Path) -> None:
    """Modular layouts nest component packages under the feature module."""
    content = _render(tmp_path, "src", "app", "modules", "billing", "controllers")
    assert (
        "from app.modules.billing.repositories.message_repository import "
        "MessageRepository" in content
    )


def test_repository_import_falls_back_without_project_anchor(tmp_path: Path) -> None:
    """Outside a project the historical bare package name is preserved."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    result = ControllerGenerator(output_dir=out).generate("Message")
    content = Path(result.files_created[0]).read_text()
    assert "from repositories.message_repository import MessageRepository" in content


# -- QK-2: create/update validate through the generated DTOs -------------


def test_create_and_update_validate_payloads(tmp_path: Path) -> None:
    """Write handlers construct the Create/Update DTOs before hitting the repo."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert "payload = MessageCreate(**body.unwrap())" in content
    assert "payload = MessageUpdate(**body.unwrap())" in content
    assert "from pydantic import ValidationError" in content
    # Partial patch semantics: only the supplied fields reach the repository.
    assert 'payload.model_dump(mode="json", exclude_unset=True)' in content


def test_read_only_controller_omits_validation_imports(tmp_path: Path) -> None:
    """A read-only controller must not import write-only symbols."""
    content = _render(tmp_path, "src", "app", "controllers", ops="list,get")
    assert "from pydantic import ValidationError" not in content
    assert "MessageCreate" not in content
    assert "InvalidMessageError" not in content
    assert "DomainError" not in content
    assert "from quadkit.result import Result" in content
    assert "from quadkit.result import Err" not in content
    assert "from quadkit.result import Ok" not in content
    assert "@post(" not in content
    assert "@put(" not in content
    assert "@delete(" not in content


# -- R3b: Result-style handlers ------------------------------------------------


def test_handlers_return_result_over_domain_errors(tmp_path: Path) -> None:
    """Fallible handlers return Result; failures are Err(domain error)."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert (
        "from quadkit.contracts.exceptions import "
        "ConflictError, DomainError, NotFoundError, "
        "ValidationError as DomainValidationError" in content
    )
    assert "from quadkit.result import Err, Ok, Result" in content
    assert "class InvalidMessageError(DomainError):" in content
    assert (
        "async def get(self, item_id: str) -> Result[dict[str, Any], NotFoundError]:"
        in content
    )
    # Write handlers sign the repository's integrity arm: restricted
    # delete / unique collision -> 409 ConflictError; missing reference
    # -> 422 contracts ValidationError (aliased: pydantic owns the name).
    assert (
        "async def delete(self, item_id: str) -> Result[dict[str, str], ConflictError | NotFoundError]:"
        in content
    )
    assert (
        "async def create(self, request: Request) -> "
        "Result[dict[str, Any], InvalidMessageError | ConflictError | "
        "DomainValidationError | NotFoundError]:" in content
    )
    # WS-8: the handler maps the repo's `Result` — serialize-or-bridge,
    # never probe. The domain error is constructed once, at the data tier.
    assert "return item.map_sync(json_serialize)" in content
    assert "return Ok(json_serialize(created.unwrap()))" in content
    assert "return Err(created.unwrap_err())" in content
    assert "return items.map_sync(" in content
    assert '"items": [json_serialize(item) for item in rows],' in content
    assert (
        'return deleted.map_sync(lambda _done: {"message": "Message deleted"})'
        in content
    )
    # No raise-style remnants: the throw path is gone from controllers.
    assert "raise NotFoundError" not in content
    assert "raise BadRequestError" not in content
    assert "quadkit.web.exceptions" not in content


def test_controller_contains_zero_outcome_probes(tmp_path: Path) -> None:
    """WS-8 pin: no handler re-reads a call result (one representation per outcome)."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert " if item is None" not in content + " "
    assert "if updated is None" not in content
    assert "if not deleted:" not in content
    # And no handler constructs a domain not-found — that is the repo's job.
    assert content.count("NotFoundError(f") == 0


def test_read_body_returns_result(tmp_path: Path) -> None:
    """The body helper parses, or carries the 400 problem as Err."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert (
        "async def _read_body(request: Request) -> Result[dict[str, Any], InvalidMessageError]:"
        in content
    )
    assert 'return Err(InvalidMessageError("Invalid JSON body"))' in content
    assert "body = await _read_body(request)" in content
    assert "if body.is_err():" in content
    assert "return Err(body.unwrap_err())" in content


def test_list_only_controller_is_result_shaped_like_every_verb(tmp_path: Path) -> None:
    """Even `list` maps the repository's ``Result`` into its envelope.

    The one raw-dict verb was the outlier every consumer notices first; one
    controller now has one return shape, and only the imports it uses.
    """
    content = _render(tmp_path, "src", "controllers", ops="list")
    assert "from quadkit.result import Result" in content
    assert "from quadkit.result import Err" not in content
    assert "from quadkit.result import Ok" not in content
    assert "from quadkit.contracts.exceptions import NotFoundError" in content
    assert ") -> Result[dict[str, Any], NotFoundError]:" in content
    assert "return items.map_sync(" in content
    assert '"items": [json_serialize(item) for item in rows],' in content
    assert '"limit": limit,' in content


def test_create_only_controller_imports_repository_not_found(tmp_path: Path) -> None:
    """Create signs the repository not-found arm even with no read verbs."""
    content = _render(tmp_path, "src", "controllers", ops="create")
    assert (
        "from quadkit.contracts.exceptions import "
        "ConflictError, DomainError, NotFoundError, "
        "ValidationError as DomainValidationError" in content
    )
    assert (
        "InvalidMessageError | ConflictError | DomainValidationError "
        "| NotFoundError" in content
    )
    assert "return Ok(json_serialize(created.unwrap()))" in content
    assert "return Err(created.unwrap_err())" in content


@pytest.mark.parametrize(
    ("ops", "expected_import", "unused_dto"),
    [
        (
            "create,get,list",
            "from domains.message import Message, MessageCreate",
            "MessageUpdate",
        ),
        (
            "update",
            "from domains.message import Message, MessageUpdate",
            "MessageCreate",
        ),
    ],
)
def test_single_write_op_imports_only_its_dto(
    tmp_path: Path, ops: str, expected_import: str, unused_dto: str
) -> None:
    """Append/read and update-only controllers carry no unused DTO import."""
    content = _render(tmp_path, "src", "controllers", ops=ops)
    assert expected_import in content
    assert unused_dto not in content


# -- QK-6: ops selection -------------------------------------------------


@pytest.mark.parametrize(
    ("ops", "expected", "absent"),
    [
        (
            "list",
            [
                '@get("/messages", response_schema_model=CrudCollectionResponse[Message], responses=ValidationErrorFilter.default_documented_responses(), result_errors=[NotFoundError])\n'
            ],
            ["@post(", "@put(", "@delete("],
        ),
        ("create", ["@post("], ["@get(", "@put(", "@delete("]),
        ("update", ["@put("], ["@get(", "@post(", "@delete("]),
        ("delete", ["@delete("], ["@get(", "@post(", "@put("]),
    ],
)
def test_ops_renders_only_requested_handlers(
    tmp_path: Path, ops: str, expected: list[str], absent: list[str]
) -> None:
    """Each operation maps to exactly its own route decorator."""
    content = _render(tmp_path, "src", "controllers", ops=ops)
    for fragment in expected:
        assert fragment in content
    for fragment in absent:
        assert fragment not in content


def test_ops_accepts_an_iterable(tmp_path: Path) -> None:
    """Callers may pass a sequence instead of a comma-separated string."""
    content = _render(tmp_path, "src", "controllers", ops=["create", "get"])
    assert "@post(" in content
    assert "@get(" in content
    assert "@put(" not in content
    assert "@delete(" not in content


def test_unknown_ops_are_rejected(tmp_path: Path) -> None:
    """A typo fails loudly instead of silently emitting an empty controller."""
    with pytest.raises(ValueError, match="Unknown controller ops"):
        _render(tmp_path, "src", "controllers", ops="list,bogus")


def test_every_ops_subset_parses_and_is_framed_consistently(tmp_path: Path) -> None:
    """Generated controllers stay syntactically valid for any operation set."""
    import ast

    for index, ops in enumerate(
        ("list", "get", "create", "update", "delete", "create,get,list")
    ):
        content = _render(tmp_path, "src", f"run{index}", "controllers", ops=ops)
        ast.parse(content)
        assert content.endswith("\n")
        assert not content.endswith("\n\n")


def test_principal_assigned_field_is_injected_from_request_state(
    tmp_path: Path,
) -> None:
    """A ``!principal`` field is injected from the authenticated request on
    create, after DTO validation, and the create fails closed without one."""
    content = _render(
        tmp_path,
        "src",
        "controllers",
        fields_str="title:str,sender_subject:str!principal",
    )
    assert "def _principal_subject(request: Request) -> str | None:" in content
    assert 'user = getattr(state, "user", None)' in content
    assert "subject = _principal_subject(request)" in content
    assert 'data["sender_subject"] = subject' in content
    assert "AuthenticationError(" in content
    assert "| AuthenticationError |" in content
    # Update never reassigns the ownership field.
    update_body = content.split("async def update", 1)[1]
    assert "sender_subject" not in update_body


def test_principal_subject_reads_every_framework_user_shape(tmp_path: Path) -> None:
    """Execute the rendered helper against the shapes ``state.user``
    actually takes in a scaffolded app.

    The stored-record *dict* (the shape the live scaffold produces)
    used to fall through ``getattr(user, "user_id", user)`` and stamp
    the stringified record into the ownership column — this test
    runs the helper, so a rendering-only check can never mask that
    class of bug again.
    """
    content = _render(
        tmp_path,
        "src",
        "controllers",
        fields_str="title:str,sender_subject:str!principal",
    )
    start = content.index("def _principal_subject")
    helper = content[start : content.index("\n\n\n", start)]
    namespace: dict[str, object] = {}
    exec("from __future__ import annotations\n" + helper, namespace)  # noqa: S102
    subject_of = namespace["_principal_subject"]

    class State:
        def __init__(self, **kw: object) -> None:
            vars(self).update(kw)

    class Req:
        def __init__(self, state: State) -> None:
            self.state = state

    class UserObj:
        user_id = "subj-obj"

    cases = {
        "framework user_id slot wins": (
            State(user_id="subj-slot", user={"user_id": "x"}),
            "subj-slot",
        ),
        "stored-record dict": (
            State(user={"user_id": "subj-dict", "email": "a@b.c"}),
            "subj-dict",
        ),
        "jwt claims dict": (State(user={"sub": "subj-claims"}), "subj-claims"),
        "user object": (State(user=UserObj()), "subj-obj"),
        "bare subject string": (State(user="subj-bare"), "subj-bare"),
        "no user at all": (State(), None),
        "record without a subject key": (State(user={"email": "a@b.c"}), None),
        "empty subject string": (State(user=""), None),
    }
    for label, (state, expected) in cases.items():
        assert subject_of(Req(state)) == expected, label  # type: ignore[operator]


def test_principal_injection_is_absent_without_create(tmp_path: Path) -> None:
    """No create handler → no principal helper, no unused auth import."""
    content = _render(
        tmp_path,
        "src",
        "controllers",
        fields_str="title:str,sender_subject:str!principal",
        ops="get,list",
    )
    assert "_principal_subject" not in content
    assert "AuthenticationError" not in content


def test_validator_options_render_enforced_write_handlers(tmp_path: Path) -> None:
    """The validator pair renders create/update enforcement returning the
    422 domain validation error with per-field errors."""
    content = _render(
        tmp_path,
        "src",
        "controllers",
        fields_str="title:str",
        validator_module="validators.message",
        validator_function="validate_message_payload",
    )
    assert "from validators.message import validate_message_payload" in content
    assert content.count("problems = validate_message_payload(data)") == 2
    assert 'code="validator_rule"' in content
    assert "FieldError" in content


def test_validator_options_must_come_as_a_pair(tmp_path: Path) -> None:
    """A half-named validator fails loudly instead of rendering unenforced."""
    with pytest.raises(ValueError, match="must be passed together"):
        _render(
            tmp_path,
            "src",
            "controllers",
            validator_module="validators.message",
        )


def test_validator_options_do_not_leak_into_read_only_controllers(
    tmp_path: Path,
) -> None:
    """Read-only op subsets never import an unused validator."""
    content = _render(
        tmp_path,
        "src",
        "controllers",
        ops="get,list",
        validator_module="validators.message",
        validator_function="validate_message_payload",
    )
    assert "validate_message_payload" not in content


@pytest.mark.parametrize("op", ["create", "update"])
def test_write_schema_uses_the_same_dto_as_payload_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    """Raw-request handlers still document their actual Pydantic input model."""
    import sys
    from types import ModuleType

    from pydantic import BaseModel

    from quadkit.web.docs.generator import OpenAPIGenerator

    class MessageCreate(BaseModel):
        title: str

    class MessageUpdate(BaseModel):
        title: str | None = None

    domain = ModuleType("domains.message")
    domain.Message = MessageCreate
    domain.MessageCreate = MessageCreate
    domain.MessageUpdate = MessageUpdate
    repository = ModuleType("repositories.message_repository")
    repository.MessageRepository = type("MessageRepository", (), {})
    monkeypatch.setitem(sys.modules, domain.__name__, domain)
    monkeypatch.setitem(sys.modules, repository.__name__, repository)
    source = _render(tmp_path, "src", "controllers", ops=op)
    namespace: dict = {}
    exec(compile(source, "<generated controller>", "exec"), namespace)  # noqa: S102
    controller = namespace["MessageController"]
    route = controller.collect_routes()[0]
    expected = MessageCreate if op == "create" else MessageUpdate
    assert route["request_model"] is expected
    spec = OpenAPIGenerator(title="test", version="1").generate_spec([controller])
    method = "post" if op == "create" else "put"
    path = "/messages" if op == "create" else "/messages/{item_id}"
    body = spec["paths"][path][method]["requestBody"]
    assert body["required"] is True
    assert body["content"]["application/json"]["schema"] == {
        "$ref": f"#/components/schemas/{expected.__name__}"
    }
    assert (
        spec["components"]["schemas"][expected.__name__] == expected.model_json_schema()
    )


def test_list_declares_native_query_binding_and_default(
    tmp_path: Path, monkeypatch
) -> None:
    import sys
    from types import ModuleType

    from pydantic import BaseModel

    from quadkit.web.docs.generator import OpenAPIGenerator

    domain = ModuleType("domains.message")
    domain.Message = type("Message", (BaseModel,), {"__annotations__": {"title": str}})
    monkeypatch.setitem(sys.modules, domain.__name__, domain)
    repository = ModuleType("repositories.message_repository")
    repository.MessageRepository = type("MessageRepository", (), {})
    monkeypatch.setitem(sys.modules, repository.__name__, repository)
    source = _render(tmp_path, "src", "controllers", ops="list")
    namespace: dict = {}
    exec(compile(source, "<generated list>", "exec"), namespace)  # noqa: S102
    controller = namespace["MessageController"]
    spec = OpenAPIGenerator("test", "1").generate_spec([controller])
    assert spec["paths"]["/messages"]["get"]["parameters"] == [
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 20},
        }
    ]


@pytest.mark.parametrize("marker", [False, 1])
def test_list_query_documentation_requires_exact_native_capability(
    tmp_path, monkeypatch, marker
):
    import ast

    from quadkit.web.filters.builtin import ValidationErrorFilter

    content = _render(tmp_path, "controllers", ops="list")
    guards = [
        node
        for node in ast.parse(content).body
        if isinstance(node, ast.If)
        and "supports_default_validation_docs_v1" in ast.unparse(node.test)
    ]
    assert len(guards) == 1
    monkeypatch.setattr(
        ValidationErrorFilter, "supports_default_validation_docs_v1", marker
    )
    with pytest.raises(RuntimeError, match="CRUD query documentation"):
        exec(  # noqa: S102 - generated capability guard
            compile(ast.Module(body=guards, type_ignores=[]), "controller.py", "exec"),
            {"ValidationErrorFilter": ValidationErrorFilter},
        )
    assert "ValidationErrorFilter" not in _render(tmp_path, "get_controller", ops="get")


@pytest.mark.parametrize("op", ["get", "list", "create", "update"])
@pytest.mark.parametrize("stamp", ["2030-06-15 00:30:45", None])
@pytest.mark.asyncio
async def test_generated_crud_serializes_only_declared_datetimes(
    tmp_path, monkeypatch, op, stamp
):
    """Execute each rendered row-returning handler, not just a template match."""
    import sys
    from types import ModuleType

    from pydantic import BaseModel
    from starlette.requests import Request

    from quadkit.result import Ok

    class Message(BaseModel):
        title: str
        stamp: datetime | None = None

    domain = ModuleType("domains.message")
    domain.Message = Message
    domain.MessageCreate = Message
    domain.MessageUpdate = Message
    repository = ModuleType("repositories.message_repository")
    repository.MessageRepository = type("MessageRepository", (), {})
    monkeypatch.setitem(sys.modules, domain.__name__, domain)
    monkeypatch.setitem(sys.modules, repository.__name__, repository)
    source = _render(
        tmp_path, "src", "controllers", ops=op, fields_str="title:str,stamp:datetime?"
    )
    namespace = {}
    exec(compile(source, "<generated datetime controller>", "exec"), namespace)  # noqa: S102
    row = {"title": "2030-06-15 00:30:45", "stamp": stamp}

    class Repo:
        async def get(self, key):
            return Ok(row)

        async def list(self, **kwargs):
            return Ok([row])

        async def create(self, data):
            return Ok(row)

        async def update(self, key, data):
            return Ok(row)

    controller = namespace["MessageController"](Repo())
    if op == "get":
        result = await controller.get("key")
    elif op == "list":
        result = await controller.list(limit=20)
    else:
        request = Request({"type": "http"})
        request._body = b'{"title":"value"}'  # noqa: SLF001 — actual body parser
        result = await (
            controller.create(request)
            if op == "create"
            else controller.update("key", request)
        )
    body = result.unwrap()
    actual = body["items"][0] if op == "list" else body
    assert actual == {
        "title": row["title"],
        "stamp": "2030-06-15T00:30:45+00:00" if stamp else None,
    }
    assert row == {"title": "2030-06-15 00:30:45", "stamp": stamp}


def test_delete_only_datetime_controller_does_not_import_unused_serializer(tmp_path):
    source = _render(
        tmp_path, "src", "controllers", ops="delete", fields_str="stamp:datetime"
    )
    assert "serialize_sql_row" not in source
