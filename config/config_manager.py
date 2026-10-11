import json
import os


config_file = "config_paths.json"


def get_shared_paths()-> dict:
    if not os.path.exists(config_file):
        return {}
    
    
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}
    
    
def add_shared_path(name: str, path: str) -> bool:
    expanded_ppath = os.path.expanduser(path)
    if not os.path.exists(expanded_ppath):
        return False
    
    paths = get_shared_paths()
    paths[name] = expanded_ppath
    
    with open(config_file, "w") as f:
        json.dump(paths, f, indent=4)
    
    return True



def remove_shared_path(name: str) -> None:
    paths = get_shared_paths()
    if name in paths:
        del paths[name]
        with open(config_file, "w") as f:
            json.dump(paths, f, indent=4)