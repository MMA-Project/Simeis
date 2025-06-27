#!/usr/bin/env python3

import toml
import subprocess
from pathlib import Path
import re
import sys

def get_workspace_members():
    cargo_toml = toml.load("Cargo.toml")
    return cargo_toml["workspace"]["members"]

def get_workspace_dependencies():
    cargo_toml = toml.load("Cargo.toml")
    return list(cargo_toml.get("workspace", {}).get("dependencies", {}).keys())

def find_rs_files(members):
    rs_files = []
    for member in members:
        for path in Path(member).rglob("src/**/*.rs"):
            rs_files.append(path)
    return rs_files

def is_dependency_used(dep, rs_files):
    pattern = re.compile(rf"\b{re.escape(dep)}\b")
    for file in rs_files:
        try:
            content = file.read_text()
            if pattern.search(content):
                return True
        except Exception:
            pass
    return False

def main():
    print("🔍 Vérification de l'utilisation des dépendances...")
    members = get_workspace_members()
    dependencies = get_workspace_dependencies()
    rs_files = find_rs_files(members)

    unused = []

    for dep in dependencies:
        if not is_dependency_used(dep, rs_files):
            unused.append(dep)

    if unused:
        print("⚠️ Dépendances non utilisées trouvées :")
        for dep in unused:
            print(f"  - {dep}")
        sys.exit(1)
    else:
        print("✅ Toutes les dépendances sont utilisées.")

if __name__ == "__main__":
    main()