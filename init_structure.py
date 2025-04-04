import os

# Folder and file structure
structure = {
    "app": [
        "__init__.py"
        "main.py",
        "models.py",
        "database.py",
        "crud.py"
    ],
    "app/templates": [
        "dashboard.html"
    ],
    "app/static": [
        "style.css",
        'header.jpg'
    ],
}

# Create folders and files
for folder, files in structure.items():
    # Create folder if it doesn't exist
    os.makedirs(folder, exist_ok=True)
    for file in files:
        # Create file if it doesn't exist
        file_path = os.path.join(folder, file)
        
        # If the file path exists do not create it
        if os.path.exists(file_path):
            print(f"⚠️ File already exists: {file_path}")
        else:
            # Create empty file
            with open(file_path, "w") as f:
                f.write("")  # create empty file

print("✅ Project structure created:")
for folder, files in structure.items():
    print(f"📁 {folder}")
    for file in files:
        print(f"  └── 📄 {file}")
