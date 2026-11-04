"""Writes an 8-week FTP plan as .zwo files: ramp tests at 1, 13 and 25 set FTP, sweet spot and threshold blocks grow week to week, VO2 work from week 2, a lighter week 4 and week 8. Usage: python3 tools/ftp_plan.py [folder], default workouts/FTP builder 8 weeks."""
import os, sys
out = sys.argv[1] if len(sys.argv) > 1 else "workouts/FTP builder 8 weeks"; os.makedirs(out, exist_ok=True)
WU = '<Warmup Duration="600" PowerLow="0.45" PowerHigh="0.70"/>'
CD = '<Cooldown Duration="360" PowerLow="0.65" PowerHigh="0.40"/>'
ss = lambda m, p: f'<SteadyState Duration="{int(m*60)}" Power="{p}"/>'
iv = lambda n, on, onp, off, offp: f'<IntervalsT Repeat="{n}" OnDuration="{int(on*60)}" OnPower="{onp}" OffDuration="{int(off*60)}" OffPower="{offp}"/>'
ramp = WU.replace('600', '300').replace('0.70', '0.50') + ''.join(ss(1, round(0.50 + 0.06 * k, 2)) for k in range(20)) + CD
ou = lambda n: ''.join(iv(4, 1, 1.05, 2, 0.95) + ss(4, 0.5) for _ in range(n))
W = [
 ('Ramp test', 'Warm up, then the target climbs every minute. Ride until you cannot hold it, then press Finish ride: your FTP is set from your best minute.', ramp),
 ('Endurance 45', 'Easy, conversational. Just spin.', WU + ss(29, 0.65) + CD),
 ('Sweet spot 3x8', 'Comfortably hard: you could talk in short sentences.', WU + iv(3, 8, 0.88, 4, 0.5) + ss(4, 0.6) + CD),
 ('Tempo 2x12', 'Steady and controlled, a bit above easy.', WU + iv(2, 12, 0.80, 5, 0.55) + CD),
 ('Sweet spot 3x10', 'Comfortably hard. Keep cadence steady.', WU + iv(3, 10, 0.90, 4, 0.5) + CD),
 ('Endurance 60', 'Easy, conversational.', WU + ss(44, 0.67) + CD),
 ('VO2 intro 5x2', 'Hard two-minute efforts with full recoveries.', WU + iv(5, 2, 1.10, 3, 0.5) + ss(5, 0.6) + CD),
 ('Sweet spot 3x12', 'Comfortably hard. Settle in.', WU + iv(3, 12, 0.90, 4, 0.5) + CD),
 ('Endurance 60 with tempo', 'Easy riding with three steady tempo blocks.', WU + ss(8, 0.65) + iv(3, 5, 0.80, 5, 0.65) + ss(6, 0.65) + CD),
 ('Threshold 4x6', 'Hard but steady: right around your FTP.', WU + iv(4, 6, 0.97, 4, 0.5) + CD),
 ('Recovery 45', 'Very easy. This is the rest week.', WU + ss(29, 0.60) + CD),
 ('Sweet spot 2x10', 'Comfortably hard, a lighter week.', WU + iv(2, 10, 0.88, 5, 0.5) + ss(8, 0.6) + CD),
 ('Ramp test', 'Retest. Ride until you cannot hold it, then Finish ride to update your FTP.', ramp),
 ('Sweet spot 2x20', 'Long sweet spot blocks. Steady breathing.', WU + iv(2, 20, 0.90, 5, 0.5) + CD),
 ('VO2 5x3', 'Hard three-minute efforts. Full recoveries.', WU + iv(5, 3, 1.12, 3, 0.5) + ss(4, 0.6) + CD),
 ('Endurance 60', 'Easy, conversational.', WU + ss(44, 0.68) + CD),
 ('Threshold 3x10', 'Around FTP, steady.', WU + iv(3, 10, 0.97, 5, 0.5) + CD),
 ('Over-unders 3 sets', 'Alternate just over and just under FTP; easy between sets.', WU + ou(3) + CD),
 ('Endurance 75 with tempo', 'Long easy ride with tempo blocks.', WU + ss(10, 0.66) + iv(3, 10, 0.80, 5, 0.66) + ss(4, 0.66) + CD),
 ('Sweet spot 3x15', 'Comfortably hard, longer blocks.', WU + iv(3, 15, 0.92, 5, 0.5) + CD),
 ('VO2 6x3', 'Hard three-minute efforts.', WU + iv(6, 3, 1.15, 3, 0.5) + CD),
 ('Threshold 2x15', 'Around FTP, two long blocks.', WU + iv(2, 15, 0.98, 6, 0.5) + ss(4, 0.6) + CD),
 ('Recovery 45', 'Very easy before the retest.', WU + ss(29, 0.60) + CD),
 ('Openers 45', 'Easy with a few short punches to feel sharp for the test.', WU + ss(10, 0.6) + iv(3, 1, 1.10, 3, 0.55) + ss(8, 0.6) + CD),
 ('Ramp test', 'Final retest. Then start the plan again from 02 at your new FTP.', ramp),
]
for k, (name, desc, body) in enumerate(W, 1):
    open(os.path.join(out, f'{k:02d} {name}.zwo'), 'w').write(f'<workout_file>\n  <author>road_renderer</author>\n  <name>{name}</name>\n  <description>{desc}</description>\n  <sportType>bike</sportType>\n  <workout>\n    ' + '\n    '.join(body.replace('/><', '/>\n<').split('\n')) + '\n  </workout>\n</workout_file>\n')
print(len(W))
