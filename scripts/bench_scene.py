# Usage on instance: blender -b -P bench_scene.py -- EEVEE|CYCLES <frames>   (synthetic scene, 1080p; for timing GPUs)
import bpy, sys, time, math, random, os
engine = sys.argv[sys.argv.index("--") + 1]
frames = int(sys.argv[sys.argv.index("--") + 2])
random.seed(1)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = "/root/out/f_"
# scene: ground + 40 subdivided monkeys with glossy materials + 3 lights
bpy.ops.mesh.primitive_plane_add(size=40)
for i in range(40):
    bpy.ops.mesh.primitive_monkey_add(location=((i % 8) * 3 - 10, (i // 8) * 3 - 6, 1))
    o = bpy.context.object
    bpy.ops.object.shade_smooth()
    o.modifiers.new("s", "SUBSURF").levels = 3
    m = bpy.data.materials.new("m%d" % i); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (random.random(), random.random(), random.random(), 1)
    b.inputs["Roughness"].default_value = 0.2
    b.inputs["Metallic"].default_value = 0.5
    o.data.materials.append(m)
for loc in [(0, -15, 12), (10, 5, 10), (-10, 5, 10)]:
    bpy.ops.object.light_add(type="AREA", location=loc); bpy.context.object.data.energy = 3000; bpy.context.object.data.size = 4
bpy.ops.object.camera_add(location=(0, -26, 12), rotation=(math.radians(65), 0, 0)); sc.camera = bpy.context.object
sc.frame_start, sc.frame_end = 1, frames
if engine == "EEVEE":
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = 64
else:
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 128
    sc.cycles.device = "GPU"
    p = bpy.context.preferences.addons["cycles"].preferences
    p.compute_device_type = os.environ.get("CYCLES_DEVICE", "CUDA")  # CUDA or OPTIX (OPTIX needs setup_instance.sh libs)
    p.get_devices()
    for d in p.devices:
        d.use = d.type == p.compute_device_type
    print("DEVICES", [(d.name, d.type, d.use) for d in p.devices])
t = time.time()
bpy.ops.render.render(animation=True)
print("RENDER_SECONDS %s %d frames %.2f" % (engine, frames, time.time() - t))
