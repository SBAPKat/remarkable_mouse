import logging
import struct
from screeninfo import get_monitors

from .common import get_monitor

logging.basicConfig(format='%(message)s')
log = logging.getLogger('remouse')

# evtype_sync = 0
# evtype_key = 1
e_type_abs = 3

# evcode_stylus_distance = 25
# evcode_stylus_xtilt = 26
# evcode_stylus_ytilt = 27
e_code_stylus_xpos = 1
e_code_stylus_ypos = 0
e_code_stylus_pressure = 24
# evcode_finger_xpos = 53
# evcode_finger_ypos = 54
# evcode_finger_pressure = 58

# wacom digitizer dimensions
wacom_width = 15725
wacom_height = 20967
# touchscreen dimensions
# finger_width = 767
# finger_height = 1023


# remap wacom coordinates to screen coordinates
def remap(x, y, wacom_width, wacom_height, monitor_width,
          monitor_height, mode, orientation, sensitivity):

    if orientation == 'bottom':
        y = wacom_height - y
    elif orientation == 'right':
        x, y = wacom_height - y, wacom_width - x
        wacom_width, wacom_height = wacom_height, wacom_width
    elif orientation == 'left':
        x, y = y, x
        wacom_width, wacom_height = wacom_height, wacom_width
    elif orientation == 'top':
        x = wacom_width - x

    ratio_width, ratio_height = monitor_width / wacom_width, monitor_height / wacom_height

    if mode == 'fill':
        scaling_x = max(ratio_width, ratio_height)
        scaling_y = scaling_x
    elif mode == 'fit':
        scaling_x = min(ratio_width, ratio_height)
        scaling_y = scaling_x
    elif mode == 'stretch':
        scaling_x = ratio_width
        scaling_y = ratio_height
    else:
        raise NotImplementedError

    return (
        scaling_x * (x - (wacom_width - monitor_width / scaling_x) / 2)* sensitivity,
        scaling_y * (y - (wacom_height - monitor_height / scaling_y) / 2)* sensitivity
    )


def read_tablet(rm_inputs, *, orientation, monitor_num, region, threshold, mode, sensitivity):
    """Loop forever and map evdev events to mouse

    Args:
        rm_inputs (dictionary of paramiko.ChannelFile): dict of pen, button
            and touch input streams
        orientation (str): tablet orientation
        monitor_num (int): monitor number to map to
        region (boolean): whether to selection mapping region with region tool
        threshold (int): pressure threshold
        mode (str): mapping mode
    """

    from pynput.mouse import Button, Controller

    lifted = True
    new_x = new_y = False

    mouse = Controller()

    monitor = get_monitor(monitor_num, region, orientation)
    log.debug('Chose monitor: {}'.format(monitor))

    while True:
        _, _, e_type, e_code, e_value = struct.unpack('2IHHi', rm_inputs['pen'].read(16))

        if e_type == e_type_abs:

            # handle x direction
            if e_code == e_code_stylus_xpos:
                log.debug(e_value)
                x = e_value
                new_x = True

            # handle y direction
            if e_code == e_code_stylus_ypos:
                log.debug('\t{}'.format(e_value))
                y = e_value
                new_y = True

            # handle draw
            if e_code == e_code_stylus_pressure:
                log.debug('\t\t{}'.format(e_value))
                if e_value > threshold:
                    if lifted:
                        log.debug('PRESS')
                        lifted = False
                        mouse.press(Button.left)
                else:
                    if not lifted:
                        log.debug('RELEASE')
                        lifted = True
                        mouse.release(Button.left)


            # only move when x and y are updated for smoother mouse
            if new_x and new_y:
                mapped_x, mapped_y = remap(
                    x, y,
                    wacom_width, wacom_height,
                    monitor.width, monitor.height,
                    mode, orientation, sensitivity
                )
                mouse.move(
                    monitor.x + mapped_x - mouse.position[0],
                    monitor.y + mapped_y - mouse.position[1]
                )
                new_x = new_y = False
