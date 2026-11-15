"""
generate_infographic.py

Reads infographic specs from content_structured.json and produces PNG files.
- type "dalle3"    → Fal AI nano-banana model (AI-generated illustration)
- type "matplotlib" → Programmatic chart from data spec
- type "none"      → Skipped

Outputs PNGs to .tmp/infographics/ and writes a manifest.json.

Usage:
    python tools/generate_infographic.py
    python tools/generate_infographic.py --content_file .tmp/content_structured.json --output_dir .tmp/infographics
"""

import argparse
import json
import os
from io import BytesIO
from pathlib import Path

import fal_client
import matplotlib
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv
from PIL import Image

matplotlib.use("Agg")  # Non-interactive backend for headless use

load_dotenv()

CONTENT_FILE = Path(".tmp/content_structured.json")
OUTPUT_DIR = Path(".tmp/infographics")


def generate_with_fal(prompt: str, output_path: Path) -> None:
    """Call Fal AI nano-banana model to generate an image."""
    os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

    print(f"  Fal AI (nano-banana): {prompt[:80]}...")
    result = fal_client.run(
        "fal-ai/nano-banana",
        arguments={
            "prompt": prompt,
            "image_size": {"width": 1024, "height": 512},
            "num_images": 1,
        },
    )

    image_url = result["images"][0]["url"]
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content)).convert("RGB")
    img.save(output_path, "PNG")
    print(f"  Saved → {output_path}")


def generate_chart(data_spec: str, output_path: Path) -> None:
    """Generate a chart from a JSON data spec using matplotlib."""
    try:
        spec = json.loads(data_spec)
    except json.JSONDecodeError:
        raise ValueError(f"matplotlib data spec is not valid JSON: {data_spec}")

    chart_type = spec.get("chart_type", "bar")
    title = spec.get("title", "")
    labels = spec.get("labels", [])
    values = spec.get("values", [])
    y_label = spec.get("y_label", "")

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8F9FA")

    colors = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51",
              "#457b9d", "#1d3557", "#a8dadc", "#e63946", "#06d6a0"]

    if chart_type == "bar":
        bars = ax.bar(labels, values, color=colors[:len(labels)], edgecolor="white", linewidth=0.5)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=10)
    elif chart_type == "horizontal_bar":
        bars = ax.barh(labels, values, color=colors[:len(labels)], edgecolor="white", linewidth=0.5)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=10)
    elif chart_type == "line":
        ax.plot(labels, values, marker="o", color=colors[0], linewidth=2.5, markersize=8)
        ax.fill_between(range(len(labels)), values, alpha=0.1, color=colors[0])
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
    elif chart_type == "pie":
        ax.pie(values, labels=labels, colors=colors[:len(labels)],
               autopct="%1.1f%%", startangle=90, pctdistance=0.85)
    else:
        ax.bar(labels, values, color=colors[:len(labels)])

    ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
    if y_label and chart_type not in ("pie",):
        ax.set_ylabel(y_label, fontsize=12)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=11)
    plt.tight_layout()

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Chart saved → {output_path}")


def run(content_file: Path = CONTENT_FILE, output_dir: Path = OUTPUT_DIR) -> dict:
    if not content_file.exists():
        raise FileNotFoundError(f"{content_file} not found. Run synthesize_content.py first.")

    content = json.loads(content_file.read_text())
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}

    for i, section in enumerate(content.get("sections", [])):
        spec = section.get("infographic", {})
        infographic_type = spec.get("type", "none")
        prompt_or_data = spec.get("prompt_or_data", "")

        if infographic_type == "none" or not prompt_or_data:
            print(f"Section {i+1} '{section['heading']}': no infographic, skipping")
            continue

        output_path = output_dir / f"section_{i+1:02d}.png"
        print(f"Section {i+1} '{section['heading']}': type={infographic_type}")

        try:
            if infographic_type == "dalle3":
                generate_with_fal(prompt_or_data, output_path)
            elif infographic_type == "matplotlib":
                generate_chart(prompt_or_data, output_path)
            else:
                print(f"  Unknown type '{infographic_type}', skipping")
                continue

            manifest[str(i)] = {
                "section_index": i,
                "section_heading": section["heading"],
                "file": str(output_path),
                "caption": spec.get("caption", ""),
            }
        except Exception as e:
            print(f"  WARNING: Failed to generate infographic for section {i+1}: {e}")
            print("  Continuing without this infographic...")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest saved → {manifest_path}")
    print(f"Generated {len(manifest)} infographic(s)")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate infographics for newsletter sections.")
    parser.add_argument("--content_file", default=str(CONTENT_FILE))
    parser.add_argument("--output_dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    run(Path(args.content_file), Path(args.output_dir))
