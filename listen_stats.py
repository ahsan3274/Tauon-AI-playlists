#!/usr/bin/env python3
"""
listen_stats.py — Analyze Tauon AI listening history
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    python listen_stats.py                     # Full report
    python listen_stats.py --top               # Top tracks/artists only
    python listen_stats.py --moods             # Mood distribution only
    python listen_stats.py --json              # Output as JSON
    python listen_stats.py --last N            # Show last N plays
    python listen_stats.py --skip-rate         # Skip analysis

Data source: ~/.local/share/TauonMusicBox/listen_history.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path


def load_history() -> list[dict]:
    history_file = os.path.expanduser("~/.local/share/TauonMusicBox/listen_history.jsonl")
    if not os.path.exists(history_file):
        print(f"No history file found at {history_file}")
        print("Listen history will be recorded once you play tracks in Tauon AI.")
        sys.exit(0)

    entries = []
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def print_full_report(entries: list[dict]) -> None:
    if not entries:
        print("No history entries recorded yet.")
        return

    total = len(entries)
    print(f"{'═' * 60}")
    print(f"  LISTEN HISTORY REPORT — {total} plays")
    print(f"{'═' * 60}")

    # Queue source distribution
    sources = Counter(e.get("source", "unknown") for e in entries)
    print(f"\n{'─' * 40}")
    print("  QUEUE SOURCES")
    print(f"{'─' * 40}")
    for src, count in sources.most_common():
        pct = count / total * 100
        bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        print(f"  {src:<20s} {count:>5d}  {pct:5.1f}%  [{bar}]")

    # Top genres
    genres = Counter(e.get("genre", "").strip() for e in entries if e.get("genre", "").strip())
    if genres:
        print(f"\n{'─' * 40}")
        print("  TOP GENRES")
        print(f"─" * 40)
        for genre, count in genres.most_common(10):
            pct = count / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {genre:<20s} {count:>5d}  {pct:5.1f}%  [{bar}]")

    # Top artists
    artists = Counter(e.get("artist", "").strip() for e in entries if e.get("artist", "").strip())
    if artists:
        print(f"\n{'─' * 40}")
        print("  TOP ARTISTS")
        print(f"{'─' * 40}")
        for artist, count in artists.most_common(10):
            pct = count / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {artist:<25s} {count:>5d}  {pct:5.1f}%  [{bar}]")

    # Audio features
    feature_entries = [e for e in entries if e.get("audio_features")]
    if feature_entries:
        print(f"\n{'─' * 40}")
        print("  AUDIO FEATURES (plays with features)")
        print(f"{'─' * 40}")

        for key in ["energy", "valence", "danceability", "acousticness", "tempo"]:
            vals = [e["audio_features"][key] for e in feature_entries if e["audio_features"].get(key) is not None]
            if vals:
                avg = sum(vals) / len(vals)
                mn = min(vals)
                mx = max(vals)
                label = key.capitalize()
                unit = " BPM" if key == "tempo" else ""
                print(f"  {label:<15s}  avg={avg:7.3f}{unit}  min={mn:7.3f}{unit}  max={mx:7.3f}{unit}")

        # Mood distribution
        moods = Counter(e.get("audio_features", {}).get("top_mood") for e in feature_entries if e.get("audio_features", {}).get("top_mood"))
        if moods:
            print(f"\n  MOOD DISTRIBUTION")
            print(f"  {'─' * 36}")
            for mood, count in moods.most_common():
                pct = count / len(feature_entries) * 100
                bar = "█" * int(pct / 2)
                print(f"    {mood:<20s} {count:>5d}  {pct:5.1f}%  [{bar}]")

        # Completion / skip rate
        completions = [e.get("completion") for e in entries if e.get("completion") is not None]
        if completions:
            avg_comp = sum(completions) / len(completions)
            skips = sum(1 for c in completions if c < 0.3)
            full_plays = sum(1 for c in completions if c >= 0.9)
            print(f"\n  COMPLETION")
            print(f"  {'─' * 36}")
            print(f"    Avg completion:    {avg_comp:.1%}")
            print(f"    Full plays (90%+): {full_plays} ({full_plays / len(completions):.1%})")
            print(f"    Skips (<30%):      {skips} ({skips / len(completions):.1%})")

    # Unique stats
    unique_tracks = len({e.get("track_id") for e in entries})
    unique_artists = len({e.get("artist") for e in entries if e.get("artist")})
    total_duration = sum(e.get("duration", 0) for e in entries)
    total_played = sum(e.get("play_duration", e.get("duration", 0)) for e in entries if e.get("play_duration"))

    print(f"\n{'─' * 40}")
    print("  SUMMARY")
    print(f"{'─' * 40}")
    print(f"    Total plays:       {total}")
    print(f"    Unique tracks:     {unique_tracks}")
    print(f"    Unique artists:    {unique_artists}")
    print(f"    Total listened:    {total_played / 3600:.1f} hours")
    print(f"{'═' * 60}")


def print_top(entries: list[dict], limit: int = 20) -> None:
    track_plays = Counter()
    for e in entries:
        key = f"{e.get('artist', '?')} — {e.get('title', '?')}"
        track_plays[key] += 1

    print(f"Top {min(limit, len(track_plays))} most played tracks:")
    for track, count in track_plays.most_common(limit):
        print(f"  {count:>4d}x  {track}")


def print_moods(entries: list[dict]) -> None:
    feature_entries = [e for e in entries if e.get("audio_features")]
    if not feature_entries:
        print("No audio features recorded yet.")
        return

    moods = Counter(e["audio_features"].get("top_mood") for e in feature_entries if e["audio_features"].get("top_mood"))
    total = len(feature_entries)

    print("Mood distribution:")
    for mood, count in moods.most_common():
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {mood:<20s} {count:>5d}  {pct:5.1f}%  [{bar}]")

    # Audio feature averages
    print("\nAudio feature averages:")
    for key in ["energy", "valence", "danceability", "acousticness", "tempo"]:
        vals = [e["audio_features"][key] for e in feature_entries if e["audio_features"].get(key) is not None]
        if vals:
            avg = sum(vals) / len(vals)
            unit = " BPM" if key == "tempo" else ""
            print(f"  {key.capitalize():<15s} {avg:.3f}{unit}")


def print_last(entries: list[dict], n: int = 10) -> None:
    recent = entries[-n:] if n > 0 else []
    if not recent:
        print("No history entries.")
        return

    print(f"Last {len(recent)} plays:")
    for e in reversed(recent):
        ts = e.get("ts", "?")[:19]
        artist = e.get("artist", "?")
        title = e.get("title", "?")
        source = e.get("source", "?")
        mood = e.get("audio_features", {}).get("top_mood", "")
        mood_str = f" [{mood}]" if mood else ""
        completion = e.get("completion")
        comp_str = f" ({completion:.0%})" if completion is not None else ""
        print(f"  {ts}  {artist} — {title}{mood_str} [{source}]{comp_str}")


def print_skip_rate(entries: list[dict]) -> None:
    completions = [e.get("completion") for e in entries if e.get("completion") is not None]
    if not completions:
        print("No completion data available. Listen to some tracks first.")
        return

    skips = sum(1 for c in completions if c < 0.3)
    partials = sum(1 for c in completions if 0.3 <= c < 0.9)
    full = sum(1 for c in completions if c >= 0.9)
    total = len(completions)

    print(f"Completion analysis ({total} tracked plays):")
    print(f"  Full plays (90%+):  {full:>5d}  ({full / total:.1%})")
    print(f"  Partial (30-90%):   {partials:>5d}  ({partials / total:.1%})")
    print(f"  Skips (<30%):       {skips:>5d}  ({skips / total:.1%})")

    # Skip rate by source
    print(f"\n  Skip rate by source:")
    for source in ["manual", "autoplay", "similarity_radio", "shuffle", "normal"]:
        src_completions = [e.get("completion") for e in entries if e.get("source") == source and e.get("completion") is not None]
        if src_completions:
            src_skips = sum(1 for c in src_completions if c < 0.3)
            print(f"    {source:<20s}  skip rate: {src_skips / len(src_completions):.1%}  ({src_skips}/{len(src_completions)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tauon AI — Listen History Stats")
    parser.add_argument("--top", action="store_true", help="Show top tracks only")
    parser.add_argument("--moods", action="store_true", help="Show mood distribution only")
    parser.add_argument("--last", type=int, metavar="N", help="Show last N plays")
    parser.add_argument("--skip-rate", action="store_true", help="Show skip analysis")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()

    entries = load_history()

    if args.as_json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return

    if args.top:
        print_top(entries)
    elif args.moods:
        print_moods(entries)
    elif args.last is not None:
        print_last(entries, args.last)
    elif args.skip_rate:
        print_skip_rate(entries)
    else:
        print_full_report(entries)


if __name__ == "__main__":
    main()
