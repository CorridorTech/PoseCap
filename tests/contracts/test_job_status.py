import pytest
from posecap_contracts import (
    JobStatus,
    JobStatusDecodeError,
    decode_job_status,
    encode_job_status,
)


def test_round_trip() -> None:
    status = JobStatus(state="running", progress=0.5, message="processing image 3 of 6")
    assert decode_job_status(encode_job_status(status)) == status


def test_terminal_states_round_trip() -> None:
    done = JobStatus(state="done", progress=1.0, message="")
    failed = JobStatus(state="failed", progress=0.25, message="webcam not found")
    assert decode_job_status(encode_job_status(done)) == done
    assert decode_job_status(encode_job_status(failed)) == failed


def test_rejects_unknown_state() -> None:
    with pytest.raises(JobStatusDecodeError, match="state"):
        decode_job_status('{"state":"exploded","progress":0.5,"message":""}')


def test_rejects_progress_out_of_range() -> None:
    with pytest.raises(JobStatusDecodeError, match="progress"):
        decode_job_status('{"state":"running","progress":1.5,"message":""}')


def test_rejects_missing_message() -> None:
    with pytest.raises(JobStatusDecodeError, match="message"):
        decode_job_status('{"state":"running","progress":0.5}')


def test_rejects_invalid_json() -> None:
    with pytest.raises(JobStatusDecodeError, match="invalid JSON"):
        decode_job_status("nope")
