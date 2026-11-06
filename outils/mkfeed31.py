"""Flux de test v3.1 : bus en course B, bus sans course (connus, dans la zone, ailleurs), autres lignes."""
import json, sys
from google.transit import gtfs_realtime_pb2 as g
T0 = int(sys.argv[1])          # horodatage de la 1re prise
def feed(ts, moves):
    f = g.FeedMessage(); f.header.gtfs_realtime_version = '2.0'; f.header.timestamp = ts
    def ent(eid, lat, lon, trip=None, route=None, vid=None, vlab=None, seq=None, stop=None, start=None, d=None, t=ts):
        e = f.entity.add(); e.id = eid; v = e.vehicle
        if trip: v.trip.trip_id = trip; v.trip.route_id = route; v.trip.start_time = start or '22:30:00'; v.trip.direction_id = d or 0
        v.position.latitude = lat; v.position.longitude = lon; v.position.bearing = 90; v.position.speed = 30
        if seq is not None: v.current_stop_sequence = seq
        if stop: v.stop_id = stop
        v.timestamp = t
        if vid: v.vehicle.id = vid
        if vlab: v.vehicle.label = vlab
    m = moves
    ent('e0', 50.6800 + m['e0'], 4.3760, 'gt:tec:T65', 'gr:tec:B0065-21803', vlab='V7777-6337', seq=12, stop='gs:tec:Bblagar1')          # bus B (libellé)
    ent('e1', 50.6000, 4.3348, 'gt:tec:T72', 'gr:tec:B0072-23739', vid='V7805-6357', seq=0, stop='gs:tec:Bnivgar5', t=T0)               # bus B (id), 1er arrêt, position figée
    ent('e2', 50.6845, 4.3766, vid='V7777-6400', t=ts)                                                                                   # sans course, bus déjà vu en B (garé)
    ent('e3', 50.6100 + m['e3'], 4.3300, vid='V9999-1')                                                                                  # sans course, inconnu, dans le BW
    ent('e4', 50.6300, 5.5700, vid='V8888-1')                                                                                            # sans course, inconnu, Liège
    ent('e5', 50.5050, 4.2359, 'gt:tec:H1', 'gr:tec:H1018-24178', vid='V7805-9999', seq=3)                                               # autre ligne, bus B connu
    ent('e6', 50.4100, 4.4400, 'gt:tec:H2', 'gr:tec:H2037-23356', vid='V5555-1', seq=5)                                                  # autre ligne, inconnu
    ent('e7', 50.6200, 4.3500)                                                                                                           # sans course et sans véhicule
    return f.SerializeToString()
open('vp_a.pb', 'wb').write(feed(T0, {'e0': 0, 'e3': 0}))
open('vp_b.pb', 'wb').write(feed(T0 + 60, {'e0': 0.002, 'e3': 0.002}))          # 1 min : e0 et e3 roulent, e2 garé
open('vp_c.pb', 'wb').write(feed(T0 + 660, {'e0': 0.004, 'e3': 0.002}))         # 11 min : e2 toujours garé → noté à nouveau
print('ok')
