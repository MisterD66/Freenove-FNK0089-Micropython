import machine
import utime
from neopixel import NeoPixel
from ir_rx.nec import NEC_8
import math

# --- ANIMATION ENGINE (Non-Blocking & Sequenced) ---
class AnimationEngine:
    def __init__(self, neopixel_obj, matrix_write_func):
        self.np = neopixel_obj
        self.matrix_func = matrix_write_func
        self.num_leds = len(self.np)
        
        # RGB State
        self.rgb_animating = False
        self.rgb_seq_active = False
        self.rgb_sequence = [] 
        self.rgb_seq_idx = 0
        self.rgb_seq_loop = False
        
        self.rgb_start_time = 0
        self.rgb_duration = 0
        self.rgb_start_colors = [(0,0,0)] * self.num_leds
        self.rgb_target_colors = [(0,0,0)] * self.num_leds
        
        # Matrix State
        self.matrix_animating = False
        self.matrix_frames = []     
        self.matrix_delay = 0       
        self.matrix_last_tick = 0
        self.matrix_idx = 0

    def fade_to(self, target, duration_ms=1000):
        # 1. Capture start
        self.rgb_start_colors = [self.np[i] for i in range(self.num_leds)]
        
        # 2. Determine target
        if isinstance(target, list) and isinstance(target[0], tuple):
            if len(target) == self.num_leds:
                self.rgb_target_colors = target
            else:
                self.rgb_target_colors = [target[0]] * self.num_leds
        else:
            self.rgb_target_colors = [target] * self.num_leds

        self.rgb_duration = duration_ms
        self.rgb_start_time = utime.ticks_ms()
        self.rgb_animating = True

    def play_rgb_sequence(self, sequence, loop=True):
        self.rgb_sequence = sequence
        self.rgb_seq_loop = loop
        self.rgb_seq_idx = 0
        self.rgb_seq_active = True
        
        # Trigger first step
        target, duration = self.rgb_sequence[0]
        self.fade_to(target, duration)

    def stop_rgb(self):
        self.rgb_animating = False
        self.rgb_seq_active = False
        self.np.fill((0,0,0))
        self.np.write()

    def play_matrix(self, frames_list, delay_ms=500):
        self.matrix_frames = frames_list
        self.matrix_delay = delay_ms
        self.matrix_idx = 0
        self.matrix_last_tick = utime.ticks_ms()
        self.matrix_animating = True
        if self.matrix_frames:
            self.matrix_func(self.matrix_frames[0])

    def stop_matrix(self):
        self.matrix_animating = False

    def update(self):
        now = utime.ticks_ms()

        # --- RGB Logic ---
        if self.rgb_animating:
            elapsed = utime.ticks_diff(now, self.rgb_start_time)
            
            if elapsed >= self.rgb_duration:
                for i in range(self.num_leds):
                    self.np[i] = self.rgb_target_colors[i]
                self.np.write()
                
                if self.rgb_seq_active:
                    self.rgb_seq_idx += 1
                    if self.rgb_seq_idx >= len(self.rgb_sequence):
                        if self.rgb_seq_loop:
                            self.rgb_seq_idx = 0
                        else:
                            self.rgb_seq_active = False
                            self.rgb_animating = False
                            return

                    target, duration = self.rgb_sequence[self.rgb_seq_idx]
                    self.fade_to(target, duration)
                else:
                    self.rgb_animating = False
            else:
                if self.rgb_duration > 0:
                    progress = elapsed / self.rgb_duration
                    for i in range(self.num_leds):
                        s = self.rgb_start_colors[i]
                        t = self.rgb_target_colors[i]
                        r = int(s[0] + (t[0] - s[0]) * progress)
                        g = int(s[1] + (t[1] - s[1]) * progress)
                        b = int(s[2] + (t[2] - s[2]) * progress)
                        self.np[i] = (r, g, b)
                    self.np.write()

        # --- Matrix Logic ---
        if self.matrix_animating and self.matrix_frames:
            if utime.ticks_diff(now, self.matrix_last_tick) > self.matrix_delay:
                self.matrix_last_tick = now
                self.matrix_idx = (self.matrix_idx + 1) % len(self.matrix_frames)
                self.matrix_func(self.matrix_frames[self.matrix_idx])

# --- I2C / HT16K33 SETUP ---
try:
    i2c = machine.SoftI2C(sda=machine.Pin(4), scl=machine.Pin(5))
    HT_ADDR = 0x71
    def init_matrix():
        i2c.writeto(HT_ADDR, b'\x21'); i2c.writeto(HT_ADDR, b'\x81'); i2c.writeto(HT_ADDR, b'\xef')
    def matrix_clear():
        i2c.writeto_mem(HT_ADDR, 0x00, b'\x00' * 16)
    def display_frame(linear_data):
        if len(linear_data) != 16: return
        interleaved = bytearray(16)
        for i in range(8):
            interleaved[i * 2] = linear_data[i]; interleaved[i * 2 + 1] = linear_data[i+8] 
        i2c.writeto_mem(HT_ADDR, 0x00, interleaved)
except Exception:
    def init_matrix(): pass
    def matrix_clear(): pass
    def display_frame(d): pass

# --- ASSETS: MATRIX ---
face1 = [0x0e, 0x11, 0x11, 0x11, 0x8e, 0x40, 0x20, 0x20, 0x20, 0x20, 0x40, 0x8e, 0x11, 0x11, 0x11, 0x0e]
face2 = [0x0e, 0x11, 0x11, 0x0e, 0x00, 0x60, 0x90, 0x90, 0x90, 0x90, 0x60, 0x00, 0x0e, 0x11, 0x11, 0x0e]
flo = [0x00, 0x7e, 0x12, 0x12, 0x02, 0x00, 0x7e, 0x40, 0x40, 0x40, 0x00, 0x3c, 0x42, 0x42, 0x3c, 0x00]
f1 = [0x06, 0x09, 0x09, 0x06, 0x00, 0x60, 0x40, 0x40, 0x40, 0x40, 0x60, 0x00, 0x06, 0x09, 0x09, 0x06]
f2 = [0x04, 0x0a, 0x0a, 0x04, 0x00, 0x60, 0x40, 0x40, 0x40, 0x40, 0x60, 0x00, 0x04, 0x0a, 0x0a, 0x04]
f3 = [0x04, 0x08, 0x08, 0x04, 0x00, 0x60, 0x40, 0x40, 0x40, 0x40, 0x60, 0x00, 0x04, 0x08, 0x08, 0x04]
f4 = [0x06, 0x09, 0x09, 0x06, 0x00, 0x60, 0x90, 0x90, 0x90, 0x90, 0x60, 0x00, 0x06, 0x09, 0x09, 0x06]

r1= [0x11, 0xd2, 0x34, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x07, 0xe4, 0x22, 0x22]
r2= [0x88, 0x4b, 0x2c, 0x00, 0xe0, 0x07, 0x00, 0x00, 0xe0, 0x07, 0x00, 0x00, 0xe0, 0x27, 0x44, 0x44]
r3= [0x44, 0x44, 0x27, 0xe0, 0x00, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x07, 0xe0, 0x00, 0x2c, 0x4b, 0x88]
r4= [0x22, 0x22, 0xe4, 0x07, 0x00, 0x00, 0xe0, 0x07, 0x00, 0x00, 0xe0, 0x07, 0x00, 0x34, 0xd2, 0x11]

k1 = [0x00, 0x00, 0x00, 0x00, 0x3c, 0x24, 0xe7, 0x81, 0x81, 0xe7, 0x24, 0x3c, 0x00, 0x00, 0x00, 0x00]
k2 = [0x00, 0x00, 0x00, 0x00, 0x3c, 0x3c, 0xff, 0xff, 0xff, 0xff, 0x3c, 0x3c, 0x00, 0x00, 0x00, 0x00]
k3 = [0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x18, 0x7e, 0x7e, 0x18, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00]
e = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

matrix_anim_talk = [face1, face2]
matrix_anim_blink = [f1, f2, f3, f2, f1, f1, f1, f4, f4, f1]
rotate = [r1,r2,r3,r4]
kreuz1 = [k3,k2,k1]
kreuz2 = [k3, e]
# --- ASSETS: RGB SEQUENCES ---
# 1. New Custom Animation (Warm White, Red, Blinking Blue)
C_WARM = (140, 100, 20)
C_RED  = (150, 0, 0)
C_BLUE = (0, 0, 150)
C_OFF  = (0, 0, 0)

# LED INDEX MAP (0-7): 
# 1->0, 8->7 (Warm)
# 4->3, 5->4 (Red)
# 2->1, 3->2 (Blue Group A)
# 6->5, 7->6 (Blue Group B)

frame_blue_A = [C_WARM, C_BLUE, C_BLUE, C_RED, C_RED, C_OFF, C_OFF, C_WARM]
frame_blue_B = [C_WARM, C_OFF, C_OFF, C_RED, C_RED, C_BLUE, C_BLUE, C_WARM]

seq_custom_blink = [
    (frame_blue_A, 300), # 300ms on A
    (frame_blue_B, 300)  # 300ms on B
]

# 2. Breathing
seq_breath = [((0, 60, 0), 1500), ((0, 2, 0), 1500)]
# 3. Police
seq_police = [((150, 0, 0), 100), ((0, 0, 0), 50), ((0, 0, 150), 100), ((0, 0, 0), 50)]
# 4. Rainbow
seq_rainbow = [((100, 0, 0), 500), ((80, 80, 0), 500), ((0, 100, 0), 500), ((0, 80, 80), 500), ((0, 0, 100), 500), ((80, 0, 80), 500)]
# 5. KITT
seq_kitt = []
for i in range(8):
    frame = [(0,0,0)] * 8; frame[i] = (150, 0, 0)
    if i > 0: frame[i-1] = (40, 0, 0)
    seq_kitt.append((frame, 100))
for i in range(6, 0, -1):
    frame = [(0,0,0)] * 8; frame[i] = (150, 0, 0)
    if i < 7: frame[i+1] = (40, 0, 0)
    seq_kitt.append((frame, 100))

# --- HARDWARE SETUP ---
leds = NeoPixel(machine.Pin(16), 8)
anim = AnimationEngine(leds, display_frame)

servos = [machine.PWM(machine.Pin(15), freq=50)]
for s in servos: s.duty_u16(4915)

motor_pins_raw = {"M1": [18, 19], "M2": [21, 20], "M3": [7, 6], "M4": [9, 8]}
motor_pwm = {}
for name, pins in motor_pins_raw.items():
    motor_pwm[name] = [machine.PWM(machine.Pin(pins[0]), freq=1000), machine.PWM(machine.Pin(pins[1]), freq=1000)]

speed = 32768 
motor_stop_time = 0

def drive(fl, fr, rl, rr, duration=0):
    global motor_stop_time
    dirs = [fl, fr, rl, rr]
    keys = ["M1", "M2", "M3", "M4"]
    for i, val in enumerate(dirs):
        p1, p2 = motor_pwm[keys[i]]
        p1.duty_u16(speed if val > 0 else 0)
        p2.duty_u16(speed if val < 0 else 0)
    if duration > 0: motor_stop_time = utime.ticks_add(utime.ticks_ms(), duration)
    else: motor_stop_time = 0

def stop(): drive(0, 0, 0, 0)

# --- IR CALLBACK ---
def ir_callback(data, addr, ctrl):
    if data < 0: return
    
    # MOVEMENT
    if data == 64: drive(1, 1, 1, 1, 400)
    elif data == 25: drive(-1, -1, -1, -1, 400)
    elif data == 7: drive(-1, 1, 1, -1, 400)
    elif data == 9: drive(1, -1, -1, 1, 400)
    elif data == 68: drive(-1, 1, -1, 1, 400)
    elif data == 67: drive(1, -1, 1, -1, 400)
    
    # RGB
    elif data == 69: anim.play_rgb_sequence(seq_police, loop=True)
    elif data == 74: anim.play_rgb_sequence(seq_custom_blink, loop=True) # <--- NEW ANIMATION (Button 2)
    elif data == 71: anim.play_rgb_sequence(seq_rainbow, loop=True)
    elif data == 21: anim.play_rgb_sequence(seq_breath, loop=True)
    elif data == 22: anim.play_rgb_sequence(seq_kitt, loop=True)
    elif data == 13: anim.stop_rgb()

    # MATRIX
    elif data == 12: anim.stop_matrix(); display_frame(face1)
    elif data == 24: anim.play_matrix(matrix_anim_talk, delay_ms=200)
    elif data == 94: anim.play_matrix(matrix_anim_blink, delay_ms=80)
    elif data == 8:  anim.stop_matrix(); display_frame(flo)
    elif data == 28: anim.play_matrix(rotate, delay_ms=80)
    elif data == 90: anim.play_matrix(kreuz1, delay_ms=300)
    elif data == 66: anim.play_matrix(kreuz2, delay_ms=300)
    elif data == 82: anim.stop_matrix(); display_frame(e)

# --- MAIN ---
def run():
    global motor_stop_time
    init_matrix()
    matrix_clear()
    ir = NEC_8(machine.Pin(3, machine.Pin.IN), ir_callback)
    print("System READY. Press Button 2 for new blink.")
    
    anim.fade_to((0, 30, 0), 1000)
    
    try:
        while True:
            anim.update()
            if motor_stop_time > 0 and utime.ticks_ms() > motor_stop_time:
                stop()
                motor_stop_time = 0
            utime.sleep_ms(10) 
    except KeyboardInterrupt:
        stop(); ir.close(); leds.fill((0,0,0)); leds.write(); matrix_clear()

run()
