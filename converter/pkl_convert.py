import os
import pickle
import json

input_folder = r'C:\\Users\\et2bo\\Downloads\\portfolio-backend-master\\portfolio-backend-master\\data_cache'
output_folder = 'output_json'

os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.endswith('.pkl'):
        with open(os.path.join(input_folder, filename), 'rb') as f:
            try:
                data = pickle.load(f)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                continue

        output_path = os.path.join(output_folder, filename.replace('.pkl', '.json'))
        try:
            data.to_json(output_path, orient='records', indent=2)
        except Exception as e:
            print(f"Failed to write {output_path}: {e}")
