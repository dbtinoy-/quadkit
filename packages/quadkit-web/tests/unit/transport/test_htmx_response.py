from quadkit import serialization as json
from quadkit.web import HTMXResponse


def test_hx_response_sets_trigger_header():
    r = HTMXResponse("<div>ok</div>", hx_trigger={"showToast": "Saved"})
    # Compare parsed JSON to handle serialization differences (spaces after colon vary)
    assert json.loads(r.headers.get("HX-Trigger")) == {"showToast": "Saved"}


def test_hx_response_sets_refresh_flag():
    r = HTMXResponse("<div>ok</div>", hx_refresh=True)
    assert r.headers.get("HX-Refresh") == "true"
