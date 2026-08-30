import argparse
from pathlib import Path
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
args = parser.parse_args()

p = Path(args.input)
if not p.exists():
    raise FileNotFoundError(p)

df = pd.read_excel(p)
print(f"Rows: {len(df)}")
print("Columns:")
for c in df.columns:
    print(" -", c)

print("\nMapping واقعی هنوز وارد نشده؛ هیچ Mapping حدسی انجام نشد.")
