bl_info = {
    "name": "Video Mocap Retarget",
    "author": "Built with Claude",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar (N) > Mocap",
    "description": "AI motion capture from MP4 video onto a rigged "
                   "character, with occlusion inference, root motion and "
                   "foot locking",
    "category": "Animation",
}


def register():
    from . import operators, properties, ui
    properties.register()
    operators.register()
    ui.register()


def unregister():
    from . import operators, properties, ui
    ui.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
