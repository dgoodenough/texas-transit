# Hand fixes to the generated names

The generator names every metro's lines and stations (DFW Transit `metro/names.py`; each network's
`urban/generated/<id>/names.csv` lists every name and why). To change one, add a row here and rerun
`METRO_HOME=urban python -m metro names <id>` from `vendor/dfw-transit` (or regenerate the metro):

- `urban/names/<id>/line_names.csv`: `line_id,name,color` (either may be blank to keep the generated one)
- `urban/names/<id>/station_renames.csv`: `station_id,new_name`

Hand fixes always win over the generated names, and survive regeneration as long as the ids do.
