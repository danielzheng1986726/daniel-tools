import os
import zipfile
import io
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC opener for Pillow
register_heif_opener()

def convert_livp_to_png(directory="."):
    """
    Scans the directory for .livp files, extracts the HEIC image, 
    and converts it to PNG in the same directory.
    """
    files = [f for f in os.listdir(directory) if f.lower().endswith(".livp")]
    
    if not files:
        print(f"No .livp files found in {os.path.abspath(directory)}")
        return

    print(f"Found {len(files)} .livp files. Starting conversion...\n")
    
    success_count = 0
    
    for filename in files:
        livp_path = os.path.join(directory, filename)
        base_name = os.path.splitext(filename)[0]
        png_path = os.path.join(directory, f"{base_name}.png")
        
        if os.path.exists(png_path):
            print(f"[SKIP] {png_path} already exists.")
            continue
            
        try:
            with zipfile.ZipFile(livp_path, 'r') as z:
                # Find the HEIC or JPG file inside the zip
                image_file = None
                for inner_file in z.namelist():
                    if inner_file.lower().endswith(('.heic', '.jpg', '.jpeg')):
                        image_file = inner_file
                        break
                
                if not image_file:
                    print(f"[WARN] No image found in {filename}")
                    continue
                
                # Read the image data
                image_data = z.read(image_file)
                
                # Convert to PNG
                image = Image.open(io.BytesIO(image_data))
                image.save(png_path, "PNG")
                
                print(f"[OK] Converted {filename} -> {base_name}.png")
                success_count += 1
                
        except zipfile.BadZipFile:
            print(f"[ERR] {filename} is not a valid zip file.")
        except Exception as e:
            print(f"[ERR] Failed to convert {filename}: {e}")

    print(f"\nDone. Successfully converted {success_count}/{len(files)} files.")

if __name__ == "__main__":
    convert_livp_to_png()
