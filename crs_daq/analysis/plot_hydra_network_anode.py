import matplotlib.pyplot as plt
import yaml
import numpy as np
import argparse
import json
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from collections import defaultdict

plt.rcParams.update({'font.size': 20})

_default_io_group = 1
_default_geometry_yaml = 'analysis/multi_tile_layout-2.3.16.yaml'

colors = ['c', 'm', 'orange', 'g']


def _default_pxy():
    return (0., 0.)


def _rotate_pixel(pixel_pos, tile_orientation):
    return pixel_pos[0]*tile_orientation[2], pixel_pos[1]*tile_orientation[1]


def parse_hydra_network(tile, iog):

    chipID_uart, missingIO = [{} for i in range(2)]
    ioc_chip = dict()
    root_chips = []
    with open("configs/iog-{}-pacman-tile-{}-hydra-network.json".format(iog, tile), 'r') as f:
        data = json.load(f)
        #missingIO = data['bad_uart_links']
        missingIO = [] #data['bad_uart_links']
        mapping = data['network']['miso_us_uart_map']
        hydra = data['network'][str(iog)]
        for ioc in hydra:
            ioc_chip[ioc] = []
            for node in hydra[ioc]["nodes"]:
                if node['chip_id'] != 'ext' and (int(node['chip_id']) < 11 or int(node['chip_id']) > 111):
                    continue
                ioc_chip[ioc].append(node['chip_id'])
                chipID_uart[node['chip_id']] = []
                if 'root' in node:
                    if node['root']:
                        l = node['miso_us']
                        for e in l:
                            if e != None:
                                root_chips.append(e)
                                break
                for i in range(len(node['miso_us'])):
                    if node['miso_us'][i] != None:
                        chipID_uart[node['chip_id']].append(mapping[i])
    return chipID_uart, missingIO, root_chips, ioc_chip

def start_end(tile, chipID, uart, chipid_pos):
    epsX = 1
    if (tile) % 2 == 0:
        epsX = -1
    epsY = 1
    if (tile) % 2 == 1:
        epsY = -1

    dX = chipid_pos[(1, tile, chipID)]['maxX'] - \
        chipid_pos[(1, tile, chipID)]['avgX']
    dY = chipid_pos[(1, tile, chipID)]['maxY'] - \
        chipid_pos[(1, tile, chipID)]['avgY']

    if uart == 2:
        start = (chipid_pos[(1, tile, chipID)]['avgX']+epsX *
                 (dX/2), chipid_pos[(1, tile, chipID)]['avgY'])
        end = (epsX * dX, 0)
    if uart == 0:
        start = (chipid_pos[(1, tile, chipID)]['avgX']-epsX *
                 (dX/2), chipid_pos[(1, tile, chipID)]['avgY'])
        end = (epsX * dX*-1, 0)
    if uart == 3:
        start = (chipid_pos[(1, tile, chipID)]['avgX'],
                 chipid_pos[(1, tile, chipID)]['avgY']+epsY*(dY/2))
        end = (0, epsY*dY)
    if uart == 1:
        start = (chipid_pos[(1, tile, chipID)]['avgX'],
                 chipid_pos[(1, tile, chipID)]['avgY']-epsY*(dY/2))
        end = (0, epsY*dY*-1)
    return start, end


def chip_to_ioc(chipID, ioc_chip):
    for ioc in ioc_chip.keys():
        if chipID in ioc_chip[str(ioc)]:
            return int(ioc)-1
    return


def plot_hydra_network(geometry_yaml, iog):
    with open(geometry_yaml) as fi:
        geo = yaml.full_load(fi)

    pixel_pitch = geo['pixel_pitch']
    chip_channel_to_position = geo['chip_channel_to_position']
    tile_orientations = geo['tile_orientations']
    tile_positions = geo['tile_positions']
    tpc_centers = geo['tpc_centers']
    tile_indeces = geo['tile_indeces']
    xs = np.array(list(chip_channel_to_position.values()))[
        :, 0] * pixel_pitch
    ys = np.array(list(chip_channel_to_position.values()))[
        :, 1] * pixel_pitch
    x_size = max(xs)-min(xs)+pixel_pitch
    y_size = max(ys)-min(ys)+pixel_pitch

    tile_geometry = defaultdict(int)
    io_group_io_channel_to_tile = {}
    geometry = defaultdict(_default_pxy)

    nonrouted_v2a_channels = [6, 7, 8, 9, 22,
                              23, 24, 25, 38, 39, 40, 54, 55, 56, 57]
    routed_v2a_channels = [i for i in range(
        64) if i not in nonrouted_v2a_channels]

    for tile in geo['tile_chip_to_io']:
        tile_orientation = tile_orientations[tile]
        tile_geometry[tile] = tile_positions[tile], tile_orientations[tile]
        for chip in geo['tile_chip_to_io'][tile]:
            io_group_io_channel = geo['tile_chip_to_io'][tile][chip]
            io_group = io_group_io_channel//1000
            io_channel = io_group_io_channel % 1000
            io_group_io_channel_to_tile[(
                io_group, io_channel)] = tile

        for chip_channel in geo['chip_channel_to_position']:
            chip = chip_channel // 1000
            channel = chip_channel % 1000
            try:
                io_group_io_channel = geo['tile_chip_to_io'][tile][chip]
            except KeyError:
                print("Chip %i on tile %i not present in network" %
                      (chip, tile))
                continue

            io_group = io_group_io_channel // 1000
            io_channel = io_group_io_channel % 1000
            x = chip_channel_to_position[chip_channel][0] * \
                pixel_pitch + pixel_pitch / 2 - x_size / 2
            y = chip_channel_to_position[chip_channel][1] * \
                pixel_pitch + pixel_pitch / 2 - y_size / 2

            x, y = _rotate_pixel((x, y), tile_orientation)
            x += tile_positions[tile][2] + \
                tpc_centers[tile_indeces[tile][0]][0]
            y += tile_positions[tile][1] + \
                tpc_centers[tile_indeces[tile][0]][1]

            geometry[(io_group, io_group_io_channel_to_tile[(
                io_group, io_channel)], chip, channel)] = x, y

    fig, ax = plt.subplots(figsize=(12, 20))
    ax.set_xlabel('X Position [mm]')
    ax.set_ylabel('Y Position [mm]')

    xmin = min(np.array(list(geometry.values()))[:, 0])-pixel_pitch/2
    xmax = max(np.array(list(geometry.values()))[:, 0])+pixel_pitch/2
    ymin = min(np.array(list(geometry.values()))[:, 1])-pixel_pitch/2
    ymax = max(np.array(list(geometry.values()))[:, 1])+pixel_pitch/2

    tile_vertical_lines = np.linspace(xmin, xmax, 3)
    tile_horizontal_lines = np.linspace(ymin, ymax, 5)
    chip_vertical_lines = np.linspace(xmin, xmax, 21)
    chip_horizontal_lines = np.linspace(ymin, ymax, 41)

    nonrouted_v2a_channels = [6, 7, 8, 9, 22,
                              23, 24, 25, 38, 39, 40, 54, 55, 56, 57]
    routed_v2a_channels = [i for i in range(
        64) if i not in nonrouted_v2a_channels]

    # ax.set_xticks(chip_vertical_lines)
    # ax.set_yticks(horizontal_lines)
    ax.set_xlim(xmin*1.1, xmax*1.1)
    ax.set_ylim(ymin*1.1, ymax*1.1)
    ax.set_aspect('equal')

    chipid_pos = dict()
    for io_group in range(1, 2):
        for tile in range((io_group-1)*8+1, (io_group-1)*8+9):
            for chip in range(11, 111):
                x = []
                y = []
                for channel in routed_v2a_channels:
                    x.append(geometry[(io_group, tile, chip, channel)][0])
                    y.append(geometry[(io_group, tile, chip, channel)][1])

                avgX = (max(x)+min(x))/2.
                avgY = (max(y)+min(y))/2.

                chipid_pos[(io_group, tile, chip)] = dict(minX=min(x), maxX=max(
                    x), avgX=avgX, minY=min(y), maxY=max(y), avgY=avgY)

                txt = plt.annotate(str(chip), [avgX, avgY], size=10,
                                   ha='center', va='center', alpha=0.7)

    for vl in tile_vertical_lines:
        ax.vlines(x=vl, ymin=ymin, ymax=ymax,
                  colors=['k'], linestyle='solid')
    for hl in tile_horizontal_lines:
        ax.hlines(y=hl, xmin=xmin, xmax=xmax,
                  colors=['k'], linestyle='solid')
    for vl in chip_vertical_lines:
        ax.vlines(x=vl, ymin=ymin, ymax=ymax,
                  colors=['k'], linestyle='dotted')
    for hl in chip_horizontal_lines:
        ax.hlines(y=hl, xmin=xmin, xmax=xmax,
                  colors=['k'], linestyle='dotted')

    for tile in range(1, 9):
        chipID_uart, missingIO, root_chips, ioc_chip = parse_hydra_network(
            tile, iog)
        #if missingIO[0] == "no test performed":
        #    missingIO = {}
        for chipID in chipID_uart.keys():
            if chipID == 'ext':
                continue
            for uart in chipID_uart[chipID]:
                start, end = start_end(
                    tile, int(chipID), uart, chipid_pos)
                plt.arrow(start[0], start[1], end[0], end[1], width=1.0,
                          color=colors[chip_to_ioc(chipID, ioc_chip) % 4], alpha=0.9)

        for chipID in chipid_pos.keys():
            if chipID[2] not in chipID_uart.keys() and chipID[1] == tile:
                r = Rectangle((chipid_pos[chipID]['minX'], chipid_pos[chipID]['minY']),
                              abs(chipid_pos[chipID]['maxX'] -
                                  chipid_pos[chipID]['minX']),
                              abs(chipid_pos[chipID]['maxY'] -
                                  chipid_pos[chipID]['minY']),
                              color='r', alpha=0.2)
                plt.gca().add_patch(r)
            if chipID[2] in root_chips and chipID[1] == tile:
                r = Rectangle((chipid_pos[chipID]['minX'], chipid_pos[chipID]['minY']),
                              abs(chipid_pos[chipID]['maxX'] -
                                  chipid_pos[chipID]['minX']),
                              abs(chipid_pos[chipID]['maxY'] -
                                  chipid_pos[chipID]['minY']),
                              color='b', alpha=0.2)
                plt.gca().add_patch(r)

    plt.title('io_group = '+str(iog))
    plt.tight_layout()
    plt.savefig('hydra-network-iog-'+str(iog)+'.png')
    print('Saved to: ', 'hydra-network-iog-'+str(iog)+'.png')


def main(io_group=_default_io_group, geometry_yaml=_default_geometry_yaml, **kwargs):
    plot_hydra_network(geometry_yaml, io_group)
    # with open(controller_config, 'r') as f:
    #     configs = json.load(f)
    # print(io_group_pacman_tile_)
    # for io_group in [4]:

    #     for itile in range(len(io_group_pacman_tile_[io_group])):
    #         network_config = configs["_include"][itile]
    #         print(network_config)
    #         tile_id = network_config.split('-')[4]
    #         # pacman_tile = controller_config.split('-')[5]
    #         filename = network_config.split('.')[0]

    #         chipID_uart, missingIO, root_chips, ioc_chip = parse_hydra_network(
    #             network_config, io_group)
    #         print(root_chips)
    #         if missingIO[0] == "no test performed":
    #             missingIO = {}
    #         plot_hydra_network(geometry_yaml, network_config,
    #                            tile_id, filename, io_group, ioc_chip)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--geometry_yaml', default=_default_geometry_yaml, type=str,
                        help='''geometry yaml (layout 2.4.0 for LArPix-v2a 10x10 tile)''')
    parser.add_argument('--io_group', default=_default_io_group,
                        type=int, help='''PACMAN IO group''')
    args = parser.parse_args()
    main(**vars(args))
