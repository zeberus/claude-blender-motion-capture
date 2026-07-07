# Video Mocap Retarget

AI-powered motion capture from MP4 video onto an existing rigged character,
inside Blender. Detects full-body 3D motion with MediaPipe Pose, reconstructs
occluded body parts (hidden legs, out-of-frame limbs), rebuilds world-space
root motion from foot contacts, and keyframes the result onto your rig.

## Requirements

- Blender 4.2+ (tested design target: 4.2–5.0)
- Internet connection for one-time setup (Python package + pose model)
- ~500 MB disk for the AI dependencies

## Installation

1. `Edit > Preferences > Add-ons > Install...` (in 4.2+: dropdown arrow >
   **Install from Disk**) and pick `video_mocap_retarget.zip`.
2. Enable **Animation: Video Mocap Retarget**.
3. Open the 3D Viewport sidebar (`N`) > **Mocap** tab.
4. Click **Install Dependencies** (installs `mediapipe` into Blender's
   Python — one time, may take a few minutes; Blender will freeze while
   installing). If Blender is installed in a protected location (e.g.
   `Program Files`), run Blender as administrator once for this step.
5. The pose model (~30 MB) downloads automatically on first analysis into
   `~/.video_mocap_retarget/`.

## Workflow

1. **Video Input** – pick your MP4. Model quality: *Heavy* is the most
   accurate (recommended), *Lite* is ~3x faster.
2. **Analyze Motion** – runs the AI pass in the background; progress shows
   in the Status box, `Esc` cancels. Analysis runs **once per video**; you
   can then re-apply with different settings instantly. *Save/Load* stores
   the analysis as `<video>.vmr.npz` next to the video.
3. **Target Rig** – pick your armature. Presets:
   - **Auto-detect** – recognizes Rigify rigs automatically (uses IK legs);
     otherwise guesses a mapping from bone names.
   - **Rigify (IK legs)** – drives `torso`, `hips`, `chest`, `neck`, `head`,
     shoulders and the FK arm chain, plus `foot_ik.L/R` and knee poles.
     IK feet give rock-solid foot plants. Sets the rig's IK/FK switches.
   - **Rigify (FK legs)** / **Mixamo** / **Unreal Mannequin** / **Custom**.
   - **Character Forward**: leave at `-Y` for standard Blender rigs.
4. **Apply Motion to Rig** – solves occlusions + root motion with the
   current settings and creates a new Action with keyframes.
   **Undo Last Application** removes it and restores the previous action
   and IK/FK switch values.

## Motion Settings

| Setting | Effect |
| --- | --- |
| Motion Speed | Playback speed multiplier for the generated keys |
| Root Motion Strength | Scales horizontal travel; `0` = animate in place |
| Foot Locking | Pins feet to the ground during detected contacts |
| Smoothing Level | 0 = raw/snappy, 1 = heavily filtered |
| Confidence Threshold | Landmarks below this visibility count as occluded and are reconstructed |

## How occlusion inference works

- **Short dropouts** (a joint vanishes under ~0.5 s) are interpolated.
- **Hidden lower body while walking/running**: cadence and gait phase are
  recovered from arm swing, shoulder sway and torso bobbing; legs are then
  synthesized with a biomechanical walk/run cycle phase-locked to the upper
  body, including foot contacts, so root motion keeps advancing.
- **Other occlusions** (arm out of frame, etc.): the last confident pose is
  held relative to the body and eased toward a neutral pose — limbs never
  freeze in world space and never snap.
- **Root motion** comes from foot-contact odometry: while a foot is planted
  it is stationary in the world, so its motion relative to the pelvis *is*
  the pelvis trajectory. Walking, running, turning and stopping — and
  traveled distance — fall out of this. Gaps are bridged with a
  cadence-based speed model.

The Status line after Apply reports what happened, e.g.
`locomotion, 6.7 m traveled, 180 leg frames inferred`.

## Custom bone mapping

Click **Export Mapping to Text** to write the resolved mapping into a text
datablock (`VMR_mapping.json`), edit target bone names in the Text Editor,
set the preset to **Custom (JSON)** and Apply. Format:

```json
{
  "name": "My rig",
  "mode": "fk",
  "root_bone": "Hips",
  "bones": {
    "root": "Hips", "spine": "Spine", "chest": "Chest",
    "neck": "Neck", "head": "Head",
    "shoulder.L": "...", "upper_arm.L": "...", "forearm.L": "...",
    "hand.L": "...", "thigh.L": "...", "shin.L": "...", "foot.L": "...",
    "toe.L": "..."
  }
}
```

`"mode": "rigify_ik"` additionally accepts an `"ik"` block with
`foot.L/foot.R` (IK foot controls) and `pole.L/pole.R` (knee pole targets).

## Notes & limitations

- Filming tips for best accuracy: one person in frame, camera roughly
  static, subject 2–6 m away, decent lighting. Handheld/moving cameras
  reduce root-motion accuracy (odometry still works, but camera motion
  bleeds into the estimate).
- Depth (toward/away from a single camera) is inherently less accurate than
  lateral motion; the foot-contact odometry compensates for locomotion but
  subtle in-place depth sway may flatten.
- Keyframing evaluates the rig once per stage per frame so Rigify
  constraints stay correct; on very long clips with heavy scenes the Apply
  step can take a minute or two.
- Fingers and facial motion are not retargeted (body-only, 33 landmarks).
- This is an offline single-camera solution: quality is comparable to other
  single-video AI mocap tools, not to multi-camera or suit-based capture.
  Expect to polish hero shots in the Graph Editor — the generated action is
  ordinary editable keyframes.
