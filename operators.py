import queue
import threading
import traceback

import bpy

from . import deps
from .retarget import mapping as mapping_mod

# Session caches (raw takes / undo records are numpy + python objects and
# live for the Blender session; the raw take can also be saved as .npz).
_CACHE = {
    "raw": None,          # analysis.pipeline.RawTake
    "undo_stack": [],     # list of undo record dicts
    "worker": None,
}


def _settings(context):
    return context.scene.vmr


def _report_error(s, msg):
    s.error = msg[:400]
    s.status = "Error"
    s.is_running = False


# ---------------------------------------------------------------------------
class VMR_OT_install_deps(bpy.types.Operator):
    bl_idname = "vmr.install_deps"
    bl_label = "Install Dependencies"
    bl_description = ("Install the 'mediapipe' AI pose-estimation package "
                      "into Blender's Python (~150 MB download, one time)")

    def execute(self, context):
        s = _settings(context)
        s.status = "Installing dependencies (Blender may freeze)..."
        s.error = ""
        err = deps.install_deps()
        if err:
            _report_error(s, err)
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        s.status = "Dependencies installed"
        self.report({'INFO'}, "mediapipe installed successfully")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
class VMR_OT_analyze(bpy.types.Operator):
    """Run AI pose analysis over the selected video (background thread)."""
    bl_idname = "vmr.analyze"
    bl_label = "Analyze Motion"
    bl_description = ("Detect full-body 3D motion in the video. Runs once "
                      "per video; settings can then be tweaked and applied "
                      "repeatedly without re-analysis")

    _timer = None

    @classmethod
    def poll(cls, context):
        s = _settings(context)
        return bool(s.video_path) and not s.is_running

    def execute(self, context):
        s = _settings(context)
        if not deps.have_deps():
            _report_error(s, "Dependencies missing - click Install "
                             "Dependencies first")
            return {'CANCELLED'}

        s.is_running = True
        s.error = ""
        s.progress = 0.0
        s.status = "Starting analysis..."
        self._q = queue.Queue()
        self._cancel = threading.Event()

        video = bpy.path.abspath(s.video_path)
        quality = s.model_quality

        def work():
            try:
                from .analysis import extract
                from .analysis.pipeline import RawTake
                res = extract.extract_landmarks(
                    video, quality,
                    progress=lambda p, m: self._q.put(("prog", p, m)),
                    cancel=self._cancel.is_set)
                raw = RawTake(world=res["world"], image=res["image"],
                              vis=res["vis"], fps=res["fps"],
                              width=res["width"], height=res["height"],
                              video_path=video)
                self._q.put(("done", raw))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self._q.put(("error", str(e)))

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        s = _settings(context)
        if event.type == 'ESC':
            self._cancel.set()
            s.status = "Cancelling..."
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        try:
            while True:
                item = self._q.get_nowait()
                kind = item[0]
                if kind == "prog":
                    _, p, m = item
                    s.progress = float(p)
                    s.status = m
                elif kind == "done":
                    raw = item[1]
                    _CACHE["raw"] = raw
                    s.has_take = True
                    s.is_running = False
                    s.progress = 1.0
                    seen = float((raw.vis > s.confidence).mean()) * 100
                    s.take_info = (f"{raw.n_frames} frames @ "
                                   f"{raw.fps:.1f} fps - "
                                   f"{seen:.0f}% joints visible")
                    s.status = "Analysis complete - ready to apply"
                    self._finish(context)
                    return {'FINISHED'}
                elif kind == "error":
                    _report_error(s, item[1])
                    self._finish(context)
                    return {'CANCELLED'}
        except queue.Empty:
            pass
        if self._cancel.is_set() and not self._thread.is_alive():
            s.is_running = False
            s.status = "Cancelled"
            self._finish(context)
            return {'CANCELLED'}
        _tag_redraw(context)
        return {'PASS_THROUGH'}

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _tag_redraw(context)


def _tag_redraw(context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


# ---------------------------------------------------------------------------
def _resolve_mapping(context, arm):
    s = _settings(context)
    names = [b.name for b in arm.data.bones]
    if s.preset == 'AUTO':
        # Prefer the Rigify preset when the rig obviously is one
        if "torso" in names and "hand_ik.L" in names and "foot_ik.L" in names:
            m = dict(mapping_mod.RIGIFY_IK)
        else:
            m = mapping_mod.guess_mapping(names)
    elif s.preset == 'CUSTOM':
        txt = bpy.data.texts.get(s.mapping_text)
        if txt is None:
            raise ValueError(
                f"Text block '{s.mapping_text}' not found - use "
                f"'Export Mapping' first, edit it, then re-apply")
        m = mapping_mod.from_json(txt.as_string())
    else:
        m = dict(mapping_mod.PRESETS[s.preset])
    problems = mapping_mod.validate(m, names)
    if problems:
        raise ValueError("Bone mapping problems: " + "; ".join(problems[:4]))
    return m


class VMR_OT_apply(bpy.types.Operator):
    bl_idname = "vmr.apply"
    bl_label = "Apply Motion to Rig"
    bl_description = ("Solve occlusions, root motion and retarget the "
                      "analyzed motion onto the target armature as keyframes")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = _settings(context)
        return s.has_take and s.target_armature and not s.is_running

    def execute(self, context):
        s = _settings(context)
        arm = s.target_armature
        raw = _CACHE.get("raw")
        if raw is None:
            _report_error(s, "No analyzed take in memory - run Analyze "
                             "Motion first")
            return {'CANCELLED'}
        try:
            mapping = _resolve_mapping(context, arm)
        except Exception as e:  # noqa: BLE001
            _report_error(s, str(e))
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        from .analysis.pipeline import Settings, build_clip
        from .retarget import apply_bpy

        try:
            s.status = "Solving motion..."
            clip = build_clip(raw, Settings(
                confidence=s.confidence, smoothing=s.smoothing,
                root_strength=s.root_strength, foot_locking=s.foot_locking,
                speed_multiplier=s.speed_multiplier))
            s.status = "Keyframing..."
            undo = apply_bpy.apply_clip(
                context, arm, clip, mapping,
                speed=s.speed_multiplier, forward=s.forward_axis,
                action_name=s.action_name,
                start_frame=s.start_frame,
                progress=lambda p, m: setattr(s, "status", m))
            _CACHE["undo_stack"].append(undo)
            d = clip.diagnostics
            loco = "locomotion" if d["locomoting"] else "in place"
            s.status = (f"Applied: {undo['frame_range'][0]}-"
                        f"{undo['frame_range'][1]} ({loco}, "
                        f"{d['distance_m']:.1f} m traveled, "
                        f"{d['synthetic_leg_frames']} leg frames inferred)")
            s.error = ""
            context.scene.frame_start = min(context.scene.frame_start,
                                            undo['frame_range'][0])
            context.scene.frame_end = max(context.scene.frame_end,
                                          undo['frame_range'][1])
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            _report_error(s, str(e))
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class VMR_OT_undo_apply(bpy.types.Operator):
    bl_idname = "vmr.undo_apply"
    bl_label = "Undo Last Application"
    bl_description = "Remove the last generated action and restore the rig"

    @classmethod
    def poll(cls, context):
        return bool(_CACHE["undo_stack"])

    def execute(self, context):
        from .retarget import apply_bpy
        undo = _CACHE["undo_stack"].pop()
        err = apply_bpy.undo_application(undo)
        s = _settings(context)
        if err:
            _report_error(s, err)
            return {'CANCELLED'}
        s.status = "Last application removed"
        return {'FINISHED'}


# ---------------------------------------------------------------------------
class VMR_OT_export_mapping(bpy.types.Operator):
    bl_idname = "vmr.export_mapping"
    bl_label = "Export Mapping to Text"
    bl_description = ("Write the currently resolved bone mapping into a text "
                      "datablock so it can be edited and used as Custom")

    @classmethod
    def poll(cls, context):
        return _settings(context).target_armature is not None

    def execute(self, context):
        s = _settings(context)
        try:
            m = _resolve_mapping(context, s.target_armature)
        except Exception:
            names = [b.name for b in s.target_armature.data.bones]
            m = mapping_mod.guess_mapping(names)
        txt = bpy.data.texts.get(s.mapping_text) or bpy.data.texts.new(
            s.mapping_text)
        txt.clear()
        txt.write(mapping_mod.to_json(m))
        s.status = f"Mapping written to text block '{txt.name}'"
        return {'FINISHED'}


class VMR_OT_save_take(bpy.types.Operator):
    bl_idname = "vmr.save_take"
    bl_label = "Save Analysis (.npz)"
    bl_description = "Save the analyzed take next to the video for reuse"

    @classmethod
    def poll(cls, context):
        return _CACHE.get("raw") is not None

    def execute(self, context):
        raw = _CACHE["raw"]
        path = bpy.path.abspath(_settings(context).video_path) + ".vmr.npz"
        raw.save(path)
        _settings(context).status = f"Saved take: {path}"
        return {'FINISHED'}


class VMR_OT_load_take(bpy.types.Operator):
    bl_idname = "vmr.load_take"
    bl_label = "Load Saved Analysis"
    bl_description = "Load a previously saved .vmr.npz take for this video"

    def execute(self, context):
        from .analysis.pipeline import RawTake
        s = _settings(context)
        path = bpy.path.abspath(s.video_path) + ".vmr.npz"
        try:
            raw = RawTake.load(path)
        except Exception as e:  # noqa: BLE001
            _report_error(s, f"Could not load take: {e}")
            return {'CANCELLED'}
        _CACHE["raw"] = raw
        s.has_take = True
        s.take_info = f"{raw.n_frames} frames @ {raw.fps:.1f} fps (loaded)"
        s.status = "Take loaded - ready to apply"
        return {'FINISHED'}


CLASSES = (VMR_OT_install_deps, VMR_OT_analyze, VMR_OT_apply,
           VMR_OT_undo_apply, VMR_OT_export_mapping, VMR_OT_save_take,
           VMR_OT_load_take)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
