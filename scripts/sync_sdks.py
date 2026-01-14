import os
import shutil
import json

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(BASE_DIR, "../nodes")  # Centralized source of all nodes
TYPES_DIR = os.path.join(BASE_DIR, "../types")  # Centralized source of all types
TEST_FLOWS_DIR = os.path.join(BASE_DIR, "../tests")  # Centralized source of all test flows
SDK_DIR = os.path.join(BASE_DIR, "../sdks")  # Engines directory
MASTER_CONFIG_PATH = os.path.join(BASE_DIR, "../nodes/all-nodes.config.json")  # Path for master config file
COMPRESSED_MASTER_CONFIG_PATH = os.path.join(BASE_DIR, "../nodes/all-nodes-simple.config.json")  # Path for compressed master config file

# Mapping of engines to their src/nodes directories and file extensions
SDK_TARGETS = {
    "nodejs": {
        "path": os.path.join(SDK_DIR, "nodejs"),
        "extensions": [".js", ".ts"]
    },
    "python": {
        "path": os.path.join(SDK_DIR, "python"),
        "extensions": [".py"]
    },
    "dotnet": {
        "path": os.path.join(SDK_DIR, "dotnet"),
        "extensions": [".cs"]
    },
}

def create_master_config():
    """
    Create a master JSON file containing all <node>.config.json data from the nodes directory.
    """
    master_config = []

    print(f"Scanning nodes directory: {NODES_DIR}")
    for node in os.listdir(NODES_DIR):
        node_path = os.path.join(NODES_DIR, node)
        print(f"Checking node: {node_path}")
        if os.path.isdir(node_path):
            config_file = os.path.join(node_path, f"{node}.config.json")
            print(f"Looking for {node}.config.json at: {config_file}")
            if os.path.exists(config_file):
                print(f"Found {node}.config.json for node {node}")
                with open(config_file, "r") as f:
                    try:
                        config_data = json.load(f)
                        config_data["id"] = node  # Add the node name as the "id"
                        master_config.append(config_data)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON for {config_file}: {e}")
            else:
                print(f"No {node}.config.json found for node {node}")

    # Write the master config to a file
    with open(MASTER_CONFIG_PATH, "w") as f:
        json.dump(master_config, f, indent=4)

    # use master_config to create a smaller config for the server, that only includes the name, id, and description in a csv format
    # add headers to the file
    with open(COMPRESSED_MASTER_CONFIG_PATH, "w") as f:
        f.write("id,display_name,description\n")
        sorted_nodes = sorted(master_config, key=lambda x: x['id'])
        for node in sorted_nodes:
            f.write(f"{node['id']},{node['display_name']},{node['description']}\n")
  
    print(f"Master configuration file created at {MASTER_CONFIG_PATH} with {len(master_config)} entries")

def copy_nodes_and_types():
    """
    Copy node files and type files into the nodes/types directories for each engine.
    Only copy process files with extensions relevant to the specific engine.
    """
    for engine, engine_info in SDK_TARGETS.items():
        target_base_dir = engine_info["path"]
        valid_extensions = engine_info["extensions"]
        
        print(f"Syncing nodes and types to {engine} engine...")

        # Prepare node directories
        target_nodes_dir = os.path.join(target_base_dir, "nodes")
        if os.path.exists(target_nodes_dir):
            shutil.rmtree(target_nodes_dir)
        os.makedirs(target_nodes_dir)

        # Copy each node directory
        for node in os.listdir(NODES_DIR):
            node_path = os.path.join(NODES_DIR, node)
            if os.path.isdir(node_path):
                target_node_dir = os.path.join(target_nodes_dir, node)
                os.makedirs(target_node_dir)

                # Copy relevant files (config files and process files with matching extensions)
                for file in os.listdir(node_path):
                    src_file = os.path.join(node_path, file)
                    dest_file = os.path.join(target_node_dir, file)
                    
                    # Always copy config files
                    if file.endswith(".json"):
                        shutil.copyfile(src_file, dest_file)
                    # Only copy process files with the right extension for this engine
                    elif any(file.endswith(ext) for ext in valid_extensions):
                        shutil.copyfile(src_file, dest_file)
                    # Copy any tests files
                    elif file.endswith(".tests.json"):
                        shutil.copyfile(src_file, dest_file)

        # Prepare types directories
        target_types_dir = os.path.join(target_base_dir, "types")
        if os.path.exists(target_types_dir):
            shutil.rmtree(target_types_dir)
        os.makedirs(target_types_dir)

        # Copy all .json files from the types directory
        for file in os.listdir(TYPES_DIR):
            if file.endswith(".json"):
                src_file = os.path.join(TYPES_DIR, file)
                dest_file = os.path.join(target_types_dir, file)
                shutil.copyfile(src_file, dest_file)

        # Prepare test flows directories
        target_test_flows_dir = os.path.join(target_base_dir, "tests/flows")
        if os.path.exists(target_test_flows_dir):
            shutil.rmtree(target_test_flows_dir)
        os.makedirs(target_test_flows_dir)

        # Copy all .json files from the test_flows directory
        for file in os.listdir(TEST_FLOWS_DIR):
            if file.endswith(".json"):
                src_file = os.path.join(TEST_FLOWS_DIR, file)
                dest_file = os.path.join(target_test_flows_dir, file)
                shutil.copyfile(src_file, dest_file)

        print(f"Nodes and types synced successfully to {engine} engine.\n")


if __name__ == "__main__":
    create_master_config()
    copy_nodes_and_types()
