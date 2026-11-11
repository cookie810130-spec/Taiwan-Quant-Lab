"""CLI: python -m quantlab.v2.import_csv 2330 path/to/2330.csv"""
import argparse
from quantlab.v2.storage import import_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="例如 2330")
    parser.add_argument("csv", help="本機 CSV 路徑，含 date/open/high/low/close/volume 欄位")
    args = parser.parse_args()
    print(import_csv(args.symbol, args.csv))


if __name__ == "__main__":
    main()
