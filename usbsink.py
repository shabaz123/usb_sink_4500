####################################
# usbsink.py
# rev 1 - November 2022 - shabaz
####################################


from machine import Pin, I2C
import time

# definitions
STUSB_SDA = Pin(4)
STUSB_SCL = Pin(5)
STUSB_I2C = I2C(0,sda = STUSB_SDA,scl = STUSB_SCL ,freq = 400000)

STUSB_RESET = Pin(14, Pin.OUT)

#Device I2C Address
STUSB_ADDRESS   =  0x28

# register definitions
DEFAULT               = 0xFF
FTP_CUST_PASSWORD_REG = 0x95
FTP_CUST_PASSWORD     = 0x47
FTP_CTRL_0            = 0x96
FTP_CUST_PWR          = 0x80 
FTP_CUST_RST_N        = 0x40
FTP_CUST_REQ          = 0x10
FTP_CUST_SECT         = 0x07
FTP_CTRL_1            = 0x97
FTP_CUST_SER          = 0xF8
FTP_CUST_OPCODE       = 0x07
RW_BUFFER             = 0x53
TX_HEADER_LOW         = 0x51
PD_COMMAND_CTRL       = 0x1A
DPM_PDO_NUMB          = 0x70
READ                  = 0x00
WRITE_PL              = 0x01
WRITE_SER             = 0x02
ERASE_SECTOR          = 0x05
PROG_SECTOR           = 0x06
SOFT_PROG_SECTOR      = 0x07
SECTOR_0              = 0x01
SECTOR_1              = 0x02
SECTOR_2              = 0x04
SECTOR_3              = 0x08
SECTOR_4              = 0x10

sector=[]

def hard_reset():
    STUSB_RESET.value(1)
    STUSB_RESET.value(0)


def reg_write_byte(reg_addr, val):
    dummyret = STUSB_I2C.writeto(STUSB_ADDRESS, bytearray([reg_addr,val]))

def reg_write(reg_addr, data):
    dummyret = STUSB_I2C.writeto(STUSB_ADDRESS, bytearray([reg_addr])+data)

def reg_read(reg_addr, qty):
    # STUSB_I2C.writeto(STUSB_ADDRESS, bytearray([reg_addr]), stop = False)
    dummyret = STUSB_I2C.writeto(STUSB_ADDRESS, bytearray([reg_addr]), False)
    rbuf = STUSB_I2C.readfrom(STUSB_ADDRESS, qty)
    return rbuf

def exit_testmode():
    reg_write_byte(FTP_CTRL_0, FTP_CUST_RST_N)
    reg_write_byte(FTP_CUST_PASSWORD_REG, 0)  # clear pw

def wait_exec():
    not_finished = True
    while not_finished:
        data = reg_read(FTP_CTRL_0, 1)
        if data[0] & FTP_CUST_REQ:
            continue
        else:
            not_finished = False

def enter_writemode(esector):
    reg_write_byte(FTP_CUST_PASSWORD_REG, FTP_CUST_PASSWORD)
    reg_write_byte(RW_BUFFER, 0)
    reg_write_byte(FTP_CTRL_0, 0)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N)
    v = ((esector << 3) & FTP_CUST_SER) | ( WRITE_SER & FTP_CUST_OPCODE)
    reg_write_byte(FTP_CTRL_1, v)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N | FTP_CUST_REQ)
    wait_exec()
    reg_write_byte(FTP_CTRL_1, SOFT_PROG_SECTOR & FTP_CUST_OPCODE)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N | FTP_CUST_REQ)
    wait_exec()
    reg_write_byte(FTP_CTRL_1, ERASE_SECTOR & FTP_CUST_OPCODE)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N | FTP_CUST_REQ)
    wait_exec()

def writesector(snum, sdata):
    reg_write(RW_BUFFER, sdata)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N)
    reg_write_byte(FTP_CTRL_1, WRITE_PL & FTP_CUST_OPCODE)
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR |FTP_CUST_RST_N | FTP_CUST_REQ)
    wait_exec()
    reg_write_byte(FTP_CTRL_1, PROG_SECTOR & FTP_CUST_OPCODE)
    v = (snum & FTP_CUST_SECT) |FTP_CUST_PWR |FTP_CUST_RST_N | FTP_CUST_REQ
    reg_write_byte(FTP_CTRL_0, v)
    wait_exec()

def set_pdonum(val):
    if val > 3:
        val = 3
    reg_write_byte(DPM_PDO_NUMB, val)

def write_pdo(pdo_num, data):
    bdata = bytearray([ data&0xff, (data>>8)&0xff, (data>>16)&0xff, (data>>24)&0xff ])
    reg_write(0x85+((pdo_num-1)*4), bdata)

def read_pdo(pdo_num):
    data = reg_read(0x85+((pdo_num-1)*4), 4)
    pdata = 0
    for i in range(0,4):
        tval = data[i]
        tval = tval << (i*8)
        pdata = pdata + tval
    return pdata

def set_voltage(pdo_num, val):
    if pdo_num < 1:
        pdo_num = 1
    elif pdo_num > 3:
        pdo_num = 3
    if val < 5:
        val = 5
    elif val > 20:
        val = 20
    if pdo_num == 1:
        val = 5
    val = val * 20
    data = read_pdo(pdo_num)
    data = data & ~(0xffc00)
    data = data | ((int(val))<<10)
    write_pdo(pdo_num, data)

def set_current(pdo_num, val):
    val = float(val)
    val = val / 0.01
    intc = int(val)
    intc = intc & 0x3ff
    pdata = read_pdo(pdo_num)
    pdata = pdata & ~(0x3ff)
    pdata = pdata | intc
    write_pdo(pdo_num, pdata)

def get_voltage(pnum):
    pdata = read_pdo(pnum)
    pdata = (pdata>>10) & 0x3ff
    volt = float(pdata) / 20.0
    return volt

def get_current(pnum):
    pdata = read_pdo(pnum)
    pdata = pdata & 0x3ff
    return float(pdata * 0.01)

def get_lowvoltlimit(pnum):
    res = 0
    if pnum == 1:  # PDO1
        res = 0
    elif pnum == 2:  # PDO2
        res = (sector[3][4]>>4) + 5
    else:  # PDO3
        res = (sector[3][6]&0x0f) + 5
    return res

def get_uppervoltlimit(pnum):
    res = 0
    if pnum == 1:  # PDO1
        res = (sector[3][3]>>4) + 5
    elif pnum == 2:  # PDO2
        res = (sector[3][5] & 0x0F) + 5
    else:
        res = (sector[3][6]>>4) + 5
    return res

def get_flexcurrent():
    fc = ((sector[4][4]&0x0F)<<6) + ((sector[4][3]&0xFC)>>2)
    return float(fc) / 100.0

def get_pdonum():
    res = reg_read(DPM_PDO_NUMB, 1)
    return res[0] & 0x07

def get_extpower():
    return (sector[3][2]&0x08)>>3

def get_usbcommcapable():
    return (sector[3][2]&0x01)

def get_configokgpio():
    return (sector[4][4]&0x60)>>5

def get_gpioctrl():
    return (sector[1][0]&0x30)>>4

def get_powerabove5vonly():
    return (sector[4][6]&0x08)>>3

def get_reqsrccurrent():
    return (sector[4][6]&0x10)>>4

def set_lowervoltagelimit(pnum, val):
    global sector
    if val < 5:
        val = 5
    elif val > 20:
        val = 20
    if pnum == 2:  # UVLO2
        sector[3][4] = sector[3][4] & 0x0f
        sector[3][4] = sector[3][4] | (val-5)<<4
    elif pnum == 3:  # UVLO3
        sector[3][6] = sector[3][6] & 0xf0
        sector[3][6] = sector[3][6] | (val-5)<<4

def set_uppervoltagelimit(pnum, val):
    global sector
    if val < 5:
        val = 5
    elif val > 20:
        val = 20
    if pnum == 1:  # OVLO1
        sector[3][3] = sector[3][3] & 0x0f
        sector[3][3] = sector[3][3] | (val-5)<<4
    elif pnum == 2:  # OVLO2
        sector[3][5] = sector[3][5] & 0xf0
        sector[3][5] = sector[3][5] | (val-5)<<4
    elif pnum == 3:  # OVLO3
        sector[3][6] = sector[3][6] & 0x0f
        sector[3][6] = sector[3][6] | (val-5)<<4

def set_flexcurrent(val):
    global sector
    val = float(val)
    if val > 5.0:
        val = 5.0
    elif val < 0.0:
        val = 0.0
    fval = int(val * 100.0)
    sector[4][3] = sector[4][3] & 0x03
    sector[4][3] = sector[4][3] | ((fval&0x3f)<<2)
    sector[4][4] = sector[4][4] & 0xf0
    sector[4][4] = sector[4][4] | ((fval&0x3c0)>>6)

def set_extpower(val):
    if val != 0:
        val = 1
    sector[3][2] = sector[3][2] & 0xF7
    sector[3][2] = sector[3][2] | (val)<<3

def set_usbcommcapable(val):
    if val != 0:
        val = 1
    sector[3][2] = sector[3][2] & 0xFe
    sector[3][2] = sector[3][2] | val

def set_configokgpio(val):
    if val < 2:
        val = 0
    elif val > 3:
        val = 3
    sector[4][4] = sector[4][4] & 0x9f
    sector[4][4] = sector[4][4] | val<<5

def set_gpioctrl(val):
    if val > 3:
        val = 3
    sector[1][0] = sector[1][0] & 0xcf
    sector[1][0] = sector[1][0] | val<<4

def set_powerabove5vonly(val):
    if val != 0:
        val = 1
    sector[4][6] = sector[4][6] & 0xf7
    sector[4][6] = sector[4][6] | val<<3

def set_reqsrccurrent(val):
    if val != 0:
        val = 1
    sector[4][6] = sector[4][6] & 0xef
    sector[4][6] = sector[4][6] | val<<4

def softreset():
    reg_write_byte(TX_HEADER_LOW, 0x0d)
    reg_write_byte(PD_COMMAND_CTRL, 0x26)


def read():
    global sector
    reg_write_byte(FTP_CUST_PASSWORD_REG, FTP_CUST_PASSWORD)  # set pw
    reg_write_byte(FTP_CTRL_0, 0x00)  # NVM controller reset
    reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N)  # PWR and RST_N
    
    sector=[]
    for i in range(0,5):
        reg_write_byte(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N)
        reg_write_byte(FTP_CTRL_1, READ & FTP_CUST_OPCODE)
        reg_write_byte(FTP_CTRL_0, (i & FTP_CUST_SECT) | FTP_CUST_PWR | FTP_CUST_RST_N | FTP_CUST_REQ)
        while True:
            rbuf = reg_read(FTP_CTRL_0, 1)
            if rbuf[0] & FTP_CUST_REQ == 0:
                break
        rbuf = reg_read(RW_BUFFER, 8)
        sector.append(rbuf)
    
    exit_testmode()

    set_pdonum((sector[3][2] & 0x06) >> 1)
    
    set_voltage(1, 5.0)  # set PDO1 to 5V
    ival = (sector[3][2] & 0xf0) >> 4
    if ival == 0:
        set_current(1, 0)
    elif ival < 11:
        set_current(1, float(ival) * 0.25 + 0.25)
    else:
        set_current(1, float(ival) * 0.50 - 2.50)
    
    set_voltage(1, ((sector[4][1]<<2)+(sector[4][0]>>6))/20.0)  # set PDO2
    ival = (sector[3][4] & 0x0f) 
    if ival == 0:
        set_current(2, 0)
    elif ival < 11:
        set_current(2, float(ival) * 0.25 + 0.25)
    else:
        set_current(2, float(ival) * 0.50 - 2.50)
    
    set_voltage(3, (((sector[4][3]&0x03)<<8)+sector[4][2])/20.0)  # set PDO1 to 5V
    ival = (sector[3][5] & 0xf0) >> 4
    if ival == 0:
        set_current(3, 0)
    elif ival < 11:
        set_current(3, float(ival) * 0.25 + 0.25)
    else:
        set_current(3, float(ival) * 0.50 - 2.50)

def write(default):
    global sector
    if default == 0:
        nvmi = [0, 0, 0]
        volt = [0.0, 0.0, 0.0]
        digv = 0

        for i in range(0,3):
            pdata = read_pdo(i+1)
            ival = float(pdata&0x3ff)*0.01
            if ival > 5.0:
                ival = 5.0  # max 5.0A current
            if ival < 0.5:
                nvmi[i] = 0
            elif ival <= 3.0:
                nvmi[i] = int(4.0*ival) - 1
            else:
                nvmi[i] = int(2.0*ival) + 5
            digv = (pdata>>10) & 0x3ff
            volt[i] = float(digv)/20.0
            if volt[i] < 5.0:
                volt[i] = 5.0  # min voltage is 5.0V
            elif volt[i] > 20.0:
                volt[i] = 20.0  # max voltage is 20V
        sector[3][2] = sector[3][2] & 0x0f
        sector[3][2] = sector[3][2] | (nvmi[0] << 4)
        sector[3][4] = sector[3][4] & 0xf0
        sector[3][4] = sector[3][4] | nvmi[1]
        sector[3][5] = sector[3][5] & 0x0f
        sector[3][5] = sector[3][5] | (nvmi[2] << 4)
        # PDO1: n/a, fixed at 5V
        # PDO2:
        digv = int(volt[1]*20.0)
        sector[4][0] = sector[4][0] & 0x3f
        sector[4][0] = sector[4][0] | ((digv&0x03)<<6)
        sector[4][1] = digv >> 2
        # PDO3:
        digv = int(volt[2]*20.0)
        sector[4][2] = 0xff & digv
        sector[4][3] = sector[4][3] & 0xfc
        sector[4][3] = sector[4][3] | (digv >> 8)

        data = reg_read(DPM_PDO_NUMB, 1)
        sector[3][2] = sector[3][2] & 0xf9
        sector[3][2] = sector[3][2] | (data[0] << 1)
        enter_writemode(SECTOR_0 | SECTOR_1  | SECTOR_2 | SECTOR_3  | SECTOR_4)
        writesector(0, sector[0])
        writesector(1, sector[1])
        writesector(2, sector[2])
        writesector(3, sector[3])
        writesector(4, sector[4])
        exit_testmode()
    else:
        def_sector=[]
        def_sector.append(bytearray([0x00, 0x00, 0xb0, 0xaa, 0x00, 0x45, 0x00, 0x00]))
        def_sector.append(bytearray([0x10, 0x40, 0x9c, 0x1c, 0xff, 0x01, 0x3c, 0xdf]))
        def_sector.append(bytearray([0x02, 0x40, 0x0f, 0x00, 0x32, 0x00, 0xfc, 0xf1]))
        def_sector.append(bytearray([0x00, 0x19, 0x56, 0xaf, 0xf5, 0x35, 0x5f, 0x00]))
        def_sector.append(bytearray([0x00, 0x4b, 0x90, 0x21, 0x43, 0x00, 0x40, 0xfb]))
        enter_writemode(SECTOR_0 | SECTOR_1  | SECTOR_2 | SECTOR_3  | SECTOR_4)
        writesector(0, def_sector[0])
        writesector(1, def_sector[1])
        writesector(2, def_sector[2])
        writesector(3, def_sector[3])
        writesector(4, def_sector[4])
        exit_testmode()


