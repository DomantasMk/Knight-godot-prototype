extends Node

## Global signal relay for cross-system communication.
##
## Systems emit here; listeners connect here. Neither side needs a reference
## to the other. Declare every cross-system signal in this file so there is a
## single place to see what the game can broadcast.
##
## Do not put logic in this file — signals only.

# --- Player ---
signal player_spawned(player: Node3D)
signal player_died
signal player_health_changed(current: int, maximum: int)

# --- Combat ---
signal damage_dealt(target: Node3D, amount: int)

# --- World ---
signal tree_hit(tree: Node3D, health_remaining: int)
signal tree_chopped(tree: Node3D)

# --- Flow ---
signal level_completed(level_id: String)
