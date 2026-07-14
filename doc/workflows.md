# Workflows

Functional flows of the system, diagrammed. This is the "how it works, step by step" companion to [ARCHITECTURE.md](../ARCHITECTURE.md) (which locks the patterns) and the [PRD](product/PRD.md) (which locks the scope). Each section: context first, then the diagram.

All flows describe the target design. Where the POC did something different that we deliberately replaced, a note says so — the evidence behind those calls is in [doc/reference/poc-verification.md](reference/poc-verification.md).

## System context

Two processes, joined by explicit contracts. Blender never imports torch; the engine never imports bpy. The addon and engine exchange data over two channels only: a localhost TCP stream for live poses, and job files on disk for batch work.

```mermaid
flowchart LR
    CAM(["Webcam"])

    subgraph ENGINE["Engine bridge process - uv venv, CUDA"]
        CAPTURE["Frame capture"]
        INFER["YOLO detect +<br/>PEAR inference"]
        STREAM["TCP pose stream<br/>server"]
        WORKER["Batch job worker"]
    end

    subgraph BLENDER["Blender process - bundled Python"]
        CLIENT["TCP client thread"]
        QUEUE["latest-wins queue"]
        TIMER["main-thread timer"]
        APPLY["core: pose mapping,<br/>keyframe policy"]
        UI["panels + operators"]
    end

    JOBS[("job dirs:<br/>images in, poses out")]

    CAM --> CAPTURE --> INFER --> STREAM
    STREAM -- "JSON frames<br/>localhost TCP" --> CLIENT --> QUEUE
    QUEUE --> TIMER --> APPLY --> UI
    UI -- "spawn / stop by PID" --> ENGINE
    UI -- "write job" --> JOBS
    JOBS <--> WORKER
```

## Live webcam streaming and Record Live MoCap

The flagship flow — verified working in the POC (20,329 successful pose loads in the last clean session). Differences from the POC: poses are pushed over TCP instead of polled from a pickle file's mtime; recording is independent of preview (POC trap: recording silently no-oped with preview off); the armature reference is validated every frame (POC's top live failure: 6,670 errors after the armature was deleted mid-stream).

```mermaid
sequenceDiagram
    actor User
    participant UI as Addon UI<br/>(main thread)
    participant BG as TCP client<br/>(background thread)
    participant ENG as Engine bridge
    participant CAM as Webcam

    User->>UI: Start Stream (device N)
    UI->>ENG: spawn process (PID tracked)
    ENG->>ENG: load models (one-time, seconds)
    UI->>BG: start client thread
    BG->>ENG: connect localhost TCP (retry until ready)

    loop every frame (~30 FPS)
        CAM->>ENG: frame
        ENG->>ENG: detect person, infer SMPL-X params
        ENG-->>BG: push JSON pose frame
        BG->>BG: overwrite latest-wins slot
        Note over UI: timer tick (main thread)
        UI->>UI: pop latest, validate armature ref
        UI->>UI: apply pose to bones (quaternions)
        opt recording active
            UI->>UI: insert keyframes at playhead
        end
    end

    User->>UI: Record Live MoCap (toggle, anytime while streaming)
    UI->>UI: start timeline playback, set recording flag

    User->>UI: Stop Stream
    UI->>ENG: terminate by PID handle
    Note over ENG: also self-terminates if<br/>Blender PID disappears
```

## Image-to-pose jobs: single capture and batch

File-based by design — the artifacts on disk are the point (poses you can re-import later). Single capture and batch share one job pipeline; the POC proved both (capture pair + two batch runs on June 8). Progress/failure sidecar text files from the POC are replaced by one status JSON per job.

```mermaid
sequenceDiagram
    actor User
    participant UI as Addon UI
    participant FS as Job dir
    participant ENG as Engine worker

    User->>UI: Capture Pose (timer) / Upload Batch Images
    UI->>FS: create job dir, write job.json<br/>(mode, images or webcam+countdown, params)
    UI->>ENG: spawn worker with job path (PID tracked)

    loop per image / after countdown
        ENG->>ENG: detect + infer
        ENG->>FS: write pose JSON (temp file + atomic rename)
        ENG->>FS: update status.json (progress 0..1)
    end

    alt success
        ENG->>FS: status.json state=done
        UI->>FS: poll status (modal timer)
        UI->>UI: load poses, apply / keyframe
    else failure
        ENG->>FS: status.json state=failed + message
        UI->>User: report error in UI (no raw traceback)
    end
```

## Target armature requirements

The stream carries SMPL-X parent-relative rotations; the addon writes them as
pose-bone local quaternions. That only lands in the right space when every
pose bone's local axes equal its SMPL-X joint frame. The binding convention
(the same one the SMPL/Meshcapade addon family uses):

* Bone names match the SMPL-X joint names (`pelvis`, `left_hip`, …,
  `right_wrist`); unnamed extras are ignored.
* In the armature's rest pose, every bone points along **+Y of SMPL-X space**
  (y-up, x = subject's left, z = toward viewer) with **roll 0**. Bone length
  is free; tails do NOT need to touch children.
* SMPL-X content is y-up: rotate the armature **object** (e.g. X+90°) to
  stand in Blender's z-up world instead of editing bone axes.

An armature whose bone tails point at their children (the classic
connected-bones build) violates this: each bone gets its own local frame, and
streamed rotations apply about the wrong axes. Symptom: some moves look right
(axes that happen to coincide) while others invert or garble — arms are the
usual tell. This was the root cause of the June 2026 "inverted arm" finding
(task 0004); the geometric repro lives in that task's 2026-07-10 notes.

## World position

There is deliberately no world-position flow: monocular pose estimation cannot recover trustworthy depth, so poses apply pelvis-locked. The POC's Arduino encoder-rig input was dropped from the product at review (too specific to one setup); the candidate future approach is software — camera tracking fused with pose estimation (PRD Roadmap: Later).

## Stream lifecycle

State machine the addon UI reflects. Failure paths are first-class: spawn timeout, socket drop, and engine crash all land back in Stopped with a reported reason — never a stuck UI (POC stopped processes by window title and had no failure states).

```mermaid
stateDiagram-v2
    [*] --> Stopped
    Stopped --> Starting: Start Stream
    Starting --> Streaming: TCP connected,<br/>first frame received
    Starting --> Stopped: spawn/connect timeout<br/>(reported)
    Streaming --> Recording: Record toggle on
    Recording --> Streaming: Record toggle off
    Streaming --> Reconnecting: socket dropped
    Recording --> Reconnecting: socket dropped
    Reconnecting --> Streaming: reconnected
    Reconnecting --> Stopped: engine process dead<br/>(reported)
    Streaming --> Stopped: Stop Stream<br/>(terminate by PID)
    Recording --> Stopped: Stop Stream<br/>(recording finalized first)
```

## Installation

The project tradeoff statement applies here hardest: a working install on the first
try beats everything. The POC's documented install path was never actually proven
(Dean ran a conda env); this flow ships tested on a clean machine. PoseCap Base is
fixed and independent of backend prerequisites. Each selected Pose Backend owns its
runtime checks, installation, doctor, and registry manifest.

```mermaid
flowchart TD
    START(["Run one PoseCap installer"]) --> SELECT{"Recommended or Custom?"}
    SELECT --> BASE["Install fixed PoseCap Base:<br/>Blender extension + registry support"]
    BASE --> PEAR{"PEAR selected?"}
    PEAR -- no --> READYBASE["Publish ready Base-only inventory"] --> DONE(["Ready"])
    PEAR -- yes --> NVIDIA{"NVIDIA driver healthy?"}
    NVIDIA -- no --> MSG["PEAR-scoped actionable message"] --> FAIL(["Stop; inventory remains installing"])
    NVIDIA -- yes --> RUNTIME["Install pinned Python, CUDA wheels,<br/>PEAR code and public weights"]
    RUNTIME --> VERIFY["PEAR doctor"]
    VERIFY --> MANIFEST["Atomically register PEAR manifest"]
    MANIFEST --> MODELS["Guide separately licensed<br/>body-model setup"]
    MODELS --> INVENTORY["Publish ready Base + PEAR inventory"] --> DONE
```

## Reading guide

| Question | Document |
|---|---|
| What is this product, who is it for | [README](../README.md), [PRD](product/PRD.md) |
| How does feature X flow, step by step | this file |
| What patterns bind the code | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| What are the engineering rules | [GUIDELINES.md](../GUIDELINES.md) |
| What did the POC actually prove | [poc-verification.md](reference/poc-verification.md) |
| Why was decision X made | [doc/adr/](adr/) |
