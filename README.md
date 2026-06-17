# Jellyfin NFO Metadata Updater

A Python script to update Jellyfin media library metadata by reading directly from NFO files. This is particularly useful when external tools have updated NFO files and you want to sync those changes to Jellyfin's internal database.

## Features

- Update Jellyfin metadata from NFO files
- Path mapping support (container vs host paths)
- Date filtering (update only recently modified files)
- Dry-run mode to preview changes
- Automatic database backups
- Support for multiple libraries at once

## Credits

This script is based on the original work by [garlandkr](https://gist.github.com/garlandkr/256fa5b691dca1960e8c441c5fc2074f), modified for generic use with additional features like path mapping and dry-run support.

## Prerequisites

- Python 3.x
- Access to Jellyfin database file
- NFO files next to your video files

## Installation

1. Clone or download this repository
2. Ensure Python 3 is installed: `python3 --version`
3. Make the script executable: `chmod +x jellyfin_nfo_updater.py`

## Usage

### Basic Usage

```bash
python3 jellyfin_nfo_updater.py --library-paths /media/movies
```

### With Path Mapping (Docker/Container Environments)

If Jellyfin runs in a container and uses different paths than your host system:

```bash
python3 jellyfin_nfo_updater.py \
  --library-paths /media/movies /media/tv \
  --path-mapping /media:/mnt/media
```

### Dry Run (Preview Changes)

See what would be updated without making changes:

```bash
python3 jellyfin_nfo_updater.py \
  --library-paths /media/movies \
  --path-mapping /media:/mnt/media \
  --dry-run
```

### Date Filtering

Update only items modified in the last 7 days:

```bash
python3 jellyfin_nfo_updater.py \
  --library-paths /media/movies \
  --path-mapping /media:/mnt/media \
  --date 7
```

### Custom Database Path

```bash
python3 jellyfin_nfo_updater.py \
  --library-paths /media/movies \
  --db-path /custom/path/to/jellyfin.db \
  --backup-dir /custom/backup/dir
```

## Arguments

- `--library-paths` (required): Library paths as seen by Jellyfin (space-separated for multiple)
- `--path-mapping`: Map container paths to host paths (format: `container_path:host_path`)
- `--db-path`: Path to Jellyfin database (default: `/var/lib/jellyfin/data/jellyfin.db`)
- `--backup-dir`: Directory for database backups (default: `/var/lib/jellyfin/backups`)
- `--date`: Age filter in days or "all" (default: `all`)
- `--datefile`: File type for date comparison: `mkv`, `nfo`, `mp4`, or `all` (default: `nfo`)
- `--dry-run`: Show changes without updating database

## Fields Updated

The script updates the following fields in Jellyfin's database:
- Name (title)
- Original title
- Overview (plot)
- Official rating (MPAA)
- Community rating
- Premiere date
- Runtime
- Studios

## Important Notes

1. **Stop Jellyfin before running**: Stop the Jellyfin service to prevent database corruption
2. **Backup creation**: The script automatically creates a timestamped backup before making changes
3. **Path mapping**: Required if Jellyfin runs in a container with different paths than the host
4. **NFO format**: Expects standard NFO XML format with fields like `title`, `plot`, `runtime`, etc.

## Example Workflow

1. Stop Jellyfin: `sudo systemctl stop jellyfin`
2. Run the script with dry-run first:
   ```bash
   python3 jellyfin_nfo_updater.py \
     --library-paths /media/movies \
     --path-mapping /media:/mnt/media \
     --dry-run
   ```
3. If satisfied, run without dry-run:
   ```bash
   python3 jellyfin_nfo_updater.py \
     --library-paths /media/movies \
     --path-mapping /media:/mnt/media
   ```
4. Start Jellyfin: `sudo systemctl start jellyfin`

## License

MIT License - See [LICENSE](LICENSE) file for details

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues or questions, please check the original script at https://gist.github.com/garlandkr/256fa5b691dca1960e8c441c5fc2074f or open an issue in this repository.