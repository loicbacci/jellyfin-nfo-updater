import sqlite3
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import argparse

parser = argparse.ArgumentParser(
    description='Update Jellyfin metadata by reading directly from NFO files.',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
examples:
  fix items where the NFO was written in the last 1 day:
    python3 jellyfin_nfo_updater.py --library-paths /media/movies --path-mapping /media:/mnt/media --date 1 --datefile nfo

  fix items where the video was added in the last 7 days:
    python3 jellyfin_nfo_updater.py --library-paths /media/tv --path-mapping /media:/mnt/media --date 7 --datefile mkv

  fix all items regardless of date:
    python3 jellyfin_nfo_updater.py --library-paths /media/movies --path-mapping /media:/mnt/media

  fix all items with dry run:
    python3 jellyfin_nfo_updater.py --library-paths /media/movies --path-mapping /media:/mnt/media --dry-run

notes:
  - stop Jellyfin before running this script
  - start Jellyfin after running this script
  - a backup of the database will be created automatically (unless dry-run)
  - fields updated: name, original title, overview, official rating,
    community rating, premiere date, runtime, studios

credits:
  - Original script by garlandkr: https://gist.github.com/garlandkr/256fa5b691dca1960e8c441c5fc2074f
  - Modified for generic use with path mapping and dry-run support
"""
)

parser.add_argument(
    '--date',
    default='all',
    metavar='DAYS|all',
    help='age filter: number of days (e.g. 1, 10) or "all" for no filter (default: all)'
)
parser.add_argument(
    '--datefile',
    choices=['mkv', 'nfo', 'mp4', 'all'],
    default='nfo',
    metavar='mkv|nfo|mp4|all',
    help='which file to use for date comparison: mkv, nfo, mp4, or all (default: nfo)'
)
parser.add_argument(
    '--backup-dir',
    default='/var/lib/jellyfin/backups',
    help='directory to store database backups (default: /var/lib/jellyfin/backups)'
)
parser.add_argument(
    '--db-path',
    default='/var/lib/jellyfin/data/jellyfin.db',
    help='path to Jellyfin database (default: /var/lib/jellyfin/data/jellyfin.db)'
)
parser.add_argument(
    '--library-paths',
    nargs='+',
    required=True,
    help='library paths to update (as seen by Jellyfin, e.g. /media/movies /media/tv)'
)
parser.add_argument(
    '--path-mapping',
    default='',
    help='map container paths to host paths (format: container_path:host_path, e.g. /media:/mnt/media)'
)
parser.add_argument(
    '--dry-run',
    action='store_true',
    help='show what would be changed without actually updating the database'
)

args = parser.parse_args()

path_mapping = {}
if args.path_mapping:
    try:
        container_path, host_path = args.path_mapping.split(':')
        path_mapping[container_path] = host_path
    except ValueError:
        print("Error: --path-mapping must be in format 'container_path:host_path'")
        exit(1)

if args.date.lower() == 'all':
    cutoff = None
    print(f"Mode: all items")
else:
    try:
        days = int(args.date)
        cutoff = datetime.now() - timedelta(days=days)
        print(f"Mode: items with {args.datefile.upper()} modified within the last {days} day(s) (since {cutoff.strftime('%Y-%m-%d %H:%M')})")
    except ValueError:
        print("Error: --date must be a number or 'all'")
        exit(1)

db_path = args.db_path
if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

backup_dir = args.backup_dir
os.makedirs(backup_dir, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = os.path.join(backup_dir, f'jellyfin.db.backup_{timestamp}')

print(f"Creating backup: {backup_path}")
if args.dry_run:
    print("DRY RUN: Skipping database backup")
else:
    try:
        shutil.copy2(db_path, backup_path)
        print("Backup created successfully")
    except Exception as ex:
        print(f"Error creating backup: {ex}")
        exit(1)

db = sqlite3.connect(db_path)
cursor = db.cursor()

path_conditions = ' OR '.join(['Path LIKE ?'] * len(args.library_paths))
path_patterns = [f'{path}%' for path in args.library_paths]

cursor.execute(f"""
    SELECT Name, Path FROM BaseItems
    WHERE ({path_conditions})
    AND (Path LIKE '%.mkv' OR Path LIKE '%.mp4' OR Path LIKE '%.avi' OR Path LIKE '%.mov')
""", path_patterns)

rows = cursor.fetchall()
fixed = 0
skipped = 0
not_found = 0
filtered = 0

_dir_cache = {}

def translate_path(container_path):
    for container_prefix, host_prefix in path_mapping.items():
        if container_path.startswith(container_prefix):
            return host_prefix + container_path[len(container_prefix):]
    return container_path

def find_nfo(video_path):
    host_video_path = translate_path(video_path)
    direct = host_video_path.rsplit('.', 1)[0] + '.nfo'
    if os.path.exists(direct):
        return direct
    dirname = os.path.dirname(host_video_path)
    target = (os.path.basename(host_video_path).rsplit('.', 1)[0] + '.nfo').lower()
    if dirname not in _dir_cache:
        try:
            _dir_cache[dirname] = os.listdir(dirname)
        except OSError:
            _dir_cache[dirname] = []
    for entry in _dir_cache[dirname]:
        if entry.lower() == target:
            return os.path.join(dirname, entry)
    return None

for name, path in rows:
    nfo_path = find_nfo(path)

    if nfo_path is None:
        not_found += 1
        continue

    if cutoff is not None:
        check_path = translate_path(path) if args.datefile != 'nfo' else nfo_path
        if not os.path.exists(check_path):
            filtered += 1
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(check_path))
        if mtime < cutoff:
            filtered += 1
            continue

    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        title       = root.findtext('title')
        orig        = root.findtext('originaltitle')
        plot        = root.findtext('plot')
        mpaa        = root.findtext('mpaa')
        premiered   = root.findtext('premiered')
        runtime     = root.findtext('runtime')

        studios = '|'.join(
            s.text.strip() for s in root.findall('studio')
            if s.text and s.text.strip()
        )

        rating_val = root.find('ratings/rating/value')
        rating = float(rating_val.text) if rating_val is not None else None

        premiere_date = None
        if premiered:
            try:
                premiere_date = datetime.strptime(premiered, '%Y-%m-%d').isoformat()
            except ValueError:
                pass

        runtime_ticks = None
        if runtime:
            try:
                runtime_ticks = int(runtime) * 60 * 10_000_000
            except ValueError:
                pass

        if not title or not title.strip():
            print(f"Skipped (no title): {nfo_path}")
            skipped += 1
            continue

        if args.dry_run:
            print(f"DRY RUN: Would update - {title.strip()} - {path}")
            fixed += 1
            continue

        cursor.execute("""
            UPDATE BaseItems SET
                Name              = ?,
                OriginalTitle     = ?,
                Overview          = ?,
                OfficialRating    = ?,
                CommunityRating   = ?,
                PremiereDate      = ?,
                RunTimeTicks      = ?,
                Studios           = ?
            WHERE Path = ?
        """, (
            title.strip(),
            orig.strip() if orig else None,
            plot.strip() if plot else None,
            mpaa.strip() if mpaa else None,
            rating,
            premiere_date,
            runtime_ticks,
            studios if studios else None,
            path
        ))

        if cursor.rowcount > 0:
            print(f"Fixed: {title.strip()} - {path}")
            fixed += 1
        else:
            print(f"No row matched: {path}")
            skipped += 1

    except Exception as ex:
        print(f"Error parsing {nfo_path}: {ex}")
        skipped += 1

if not args.dry_run:
    db.commit()
else:
    print("DRY RUN: Skipping database commit")

db.close()

dry_run_suffix = " (DRY RUN)" if args.dry_run else ""

print(f"""
Summary:
  Fixed:                  {fixed}
  Skipped:                {skipped}
  Missing NFO:            {not_found}
  Filtered by date:       {filtered}
  Database backup:        {backup_path}
""")
