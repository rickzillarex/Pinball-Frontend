import os
import shutil
import zipfile
from pathlib import Path

def create_bundle():
    # Paths
    dist_dir = Path('dist')
    bundle_dir = dist_dir / 'pinball-cabinet-bundle'
    
    # Clean and create
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy .exe files
    for exe in dist_dir.glob('*.exe'):
        shutil.copy(exe, bundle_dir / exe.name)
    
    # Copy JSON templates
    for json_file in ['config.json', 'tables.json', 'README.md']:
        if Path(json_file).exists():
            shutil.copy(json_file, bundle_dir / json_file)
    
    # Create table-manager subfolder and copy web app files
    tm_dir = bundle_dir / 'table-manager'
    tm_dir.mkdir(exist_ok=True)
    
    for web_file in ['index.html', 'app.js', 'styles.css']:
        if Path(web_file).exists():
            shutil.copy(web_file, tm_dir / web_file)
    
    # Create zip
    zip_path = dist_dir / 'pinball-cabinet-bundle.zip'
    if zip_path.exists():
        zip_path.unlink()
    
    shutil.make_archive(
        str(dist_dir / 'pinball-cabinet-bundle'),
        'zip',
        bundle_dir
    )
    
    print(f'Bundle created: {zip_path}')

if __name__ == '__main__':
    create_bundle()
