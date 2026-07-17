#!/usr/bin/env python3

from argparse import ArgumentParser
import csv
from pathlib import Path
import re
import shutil
import subprocess

parser = ArgumentParser()

parser.add_argument('project', type=Path)

args = parser.parse_args()

project_dir = args.project
project_name = project_dir.name
pcb_file = project_name + '.kicad_pcb'
sch_file = project_name + '.kicad_sch'

dist_dir = project_dir / 'dist'
gerber_dir = dist_dir / 'gerber'
if dist_dir.exists():
    shutil.rmtree(dist_dir)

def kicad(cmd):
    subprocess.run(
        args=['kicad-cli'] + cmd,
        check=True,
        cwd=project_dir,
    )

kicad([
    'pcb', 'export', 'gerbers',
    '--layers', ','.join([
        'F.Cu', 'B.Cu',
        'F.Mask', 'B.Mask',
        'F.Paste',
        'F.Silkscreen', 'B.Silkscreen',
        'Edge.Cuts',
    ]),
    '--no-protel-ext',
    '--output', 'dist/gerber',
    pcb_file,
])

kicad([
    'pcb', 'export', 'drill',
    '--output', 'dist/gerber',
    pcb_file,
])

shutil.make_archive(
    base_name=dist_dir / project_name,
    format='zip',
    root_dir=gerber_dir,
)

kicad([
    'pcb', 'export', 'pdf',
    '--mode-multipage',
    '--include-border-title',
    '--layers', 'F.Fab,B.Fab',
    '--common-layers', 'Edge.Cuts',
    '--crossout-DNP-footprints-on-fab-layers',
    '--output', 'dist/' + project_name + '-fab.pdf',
    pcb_file,
])

jlc_pos_file = dist_dir / (project_name + '-pos-jlc.csv')
kicad([
    'pcb', 'export', 'pos',
    '--format', 'csv',
    '--units', 'mm',
    '--use-drill-file-origin',
    '--output', 'dist/' + jlc_pos_file.name,
    pcb_file,
])

with open(jlc_pos_file, 'rt') as infile:
    jlc_pos_file.unlink()
    with open(jlc_pos_file, 'wt', encoding='utf-16') as outfile:
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)
        writer.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for row in reader:
            writer.writerow([
                row['Ref'],
                float(row['PosX']),
                float(row['PosY']),
                row['Side'],
                float(row['Rot']),
            ])

jlc_bom_file = dist_dir / (project_name + '-bom-jlc.csv')
jlc_bom_fields = {
    'Reference': 'Designator',
    'BOM Value': 'Comment',
    'Footprint': 'Footprint',
    'LCSC': 'JLCPCB Part #',
}
kicad([
    'sch', 'export', 'bom',
    '--format-preset', 'CSV',
    '--fields', ','.join(jlc_bom_fields.keys()),
    '--labels', ','.join(jlc_bom_fields.values()),
    '--group-by', 'BOM Value,Footprint',
    '--exclude-dnp',
    '--output', 'dist/' + jlc_bom_file.name,
    sch_file,
])

with open(jlc_bom_file, 'rt') as infile:
    jlc_bom_file.unlink()
    with open(jlc_bom_file, 'wt', encoding='utf-16') as outfile:
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, reader.fieldnames)
        writer.writeheader()
        for row in reader:
            # JLCPCB is confused by the metric sizes in footprint names
            row['Footprint'] = re.sub(r'_\d+Metric', '', row['Footprint'])

            writer.writerow(row)

kicad([
    'sch', 'export', 'pdf',
    '--output', 'dist/' + project_name + '-sch.pdf',
    sch_file,
])
