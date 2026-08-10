@tool
extends EditorScenePostImport

## Import script for GLBs whose colour lives in vertex colours instead of a texture.
##
## Godot's glTF importer reads COLOR_0 into the mesh but never sets
## StandardMaterial3D.vertex_color_use_as_albedo, so the asset imports pure white and the
## colour data sits there unused. Flipping the flag here fixes it once, at import time, for
## every scene that instances the model — the alternative is walking the imported subtree
## from each entity's _ready(), which pays the cost every spawn and is easy to forget.
##
## Wire it up per asset in the .glb.import file:
##     import_script/path="res://tools/import/vertex_color_material.gd"


func _post_import(scene: Node) -> Object:
	_enable_vertex_colors(scene)
	return scene


func _enable_vertex_colors(node: Node) -> void:
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		var mesh := mesh_instance.mesh
		for surface in mesh.get_surface_count():
			var material := mesh.surface_get_material(surface) as StandardMaterial3D
			if material:
				material.vertex_color_use_as_albedo = true

	for child in node.get_children():
		_enable_vertex_colors(child)
