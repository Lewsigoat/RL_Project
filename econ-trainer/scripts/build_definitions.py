#!/usr/bin/env python3
"""Rebuild src/data JSON from Lucas's Edexcel IGCSE EC2 notes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_ec2 import main

if __name__ == "__main__":
    main()
