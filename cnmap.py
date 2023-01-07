#!/usr/bin/env python3
import curses
from curses.textpad import Textbox, rectangle
from math import floor
from os import getuid,path
import nmap
import subprocess

VERSION_STRING = '0.0.1.1'
ScanModes = [
            {'name':'Ping Scan','param':'-sn','root':False},
            {'name':'TCP SYN Scan','param':'-sS','root':True},
            {'name':'TCP(SYN)+OS','param':'-sS -O -T4','root':True},
            {'name':'UDP Scan','param':'-sU','root':True}
            ]

current_uid = getuid()

class ScanOptions():
    ip_address = ''
    mode = 0

# Helper function that we call when we are initializing curses
def init_application():
    scr = curses.initscr()
    curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2,curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(3,curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(4,curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(5,curses.COLOR_BLUE, curses.COLOR_WHITE)
    scr.keypad(True)
    curses.curs_set(0)
    curses.noecho()
    return scr

# Helper function that we call to initialize new dialog windows
def init_dialog(height:int, width:int, pos_y:int, pos_x:int,color_pair:int,title:str):
    try:
        dialog= curses.newwin(height,width,pos_y,pos_x)
        dialog.border(curses.ACS_VLINE,curses.ACS_VLINE,curses.ACS_HLINE,curses.ACS_HLINE,curses.ACS_ULCORNER,curses.ACS_URCORNER,curses.ACS_LLCORNER,curses.ACS_LRCORNER)
        dialog.bkgd(' ',curses.color_pair(color_pair))
        dialog.timeout(10)
        dialog.addstr(0,2,f'[{title}]')
        return dialog
    except:
        return None

#--------------- Beginning of Reusable dialogs section ---------------
def error_dialog(title:str,message:str):
    msglen = len(message)
    win = init_dialog(4,msglen+4,floor(curses.LINES / 2),floor(curses.COLS / 2 - msglen/ 2 -2),3,title)
    win.addstr(1,2,message,curses.color_pair(4))
    win.addstr(2,2,'Press ENTER to continue')
    win.redrawwin()
    win.refresh()
    while(True):
        keypressed = win.getch()
        if keypressed in [10, 13, curses.KEY_ENTER, curses.ascii.BEL, curses.KEY_EXIT] :
            break
    del(win)

def input_dialog(title:str, message:str, default_text:str, max_length:int):
    msglen = len(message)
    if (msglen >= max_length) or (max_length >= curses.COLS -4):
        win = init_dialog(5,msglen+4,floor(curses.LINES / 2),floor(curses.COLS / 2 - msglen/ 2 -2),2,title)
    else:
        win = init_dialog(5,max_length+4,floor(curses.LINES / 2),floor(curses.COLS / 2 - max_length/ 2 -2),2,title)
    win.addstr(2,2,message)
    result = default_text
    win.addstr(3,2,result)
    win.refresh()
    while(True):
        keypressed = win.getch()
        if (keypressed == curses.KEY_BACKSPACE) or (keypressed == 127) or (keypressed == ord("\b")):
            if (msglen >= max_length) or (max_length >= curses.COLS -4):
                for i in range(msglen -4 ):
                    win.addch(3,2+i,' ')
            else:
                for i in range(max_length):
                    win.addch(3,2+i,' ')
            result = result[:-1]
            win.addstr(3,2,result)
            win.refresh()
        elif (keypressed == curses.KEY_ENTER) or (keypressed in [10,13]):
            del(win)
            return result
        elif(keypressed >=32) and (keypressed <=126) :
            result += chr(keypressed)
            win.addstr(3,2,result)
            win.refresh()

def choice_dialog(title:str, message:str,choices =[]):
    msglen = len(message)
    itemindex = 0 #this will hold the selected choice
    win = init_dialog(8,msglen+4,floor(curses.LINES / 2),floor(curses.COLS / 2 - msglen/ 2 -2),2,title) # Make the window centered
    win.keypad(True) #we are using up and arrow keys so we need the keypad to be True
    # render the widgets with the defaults
    win.addstr(2,2,message)
    rectangle(win,4,1,6,msglen)
    win.addstr(5,2,str(choices[0])[0:msglen-2],curses.color_pair(2))
    win.addch(5,msglen-1,curses.ACS_DARROW) 
    while(True):
        keypressed = win.getch()
        if (keypressed == curses.KEY_ENTER) or (keypressed in [10,13]):
            return itemindex
        elif keypressed == curses.KEY_DOWN:
            if itemindex < len(choices)-1: #check if we are not on the last item of the choice list
                itemindex += 1
            # Render the new choice on the widget
            for i in range(msglen-2):
                win.addch(5,2+i,' ',curses.color_pair(2))
            win.addstr(5,2,str(choices[itemindex])[0:msglen-6],curses.color_pair(2))
            win.addch(5,msglen-1,curses.ACS_DARROW)
            win.refresh()
        elif keypressed == curses.KEY_UP:
            if itemindex > 0: #check if we are not on the first item of the choice list
                itemindex -= 1
            # Render the new choice on the widget
            for i in range(msglen-2):
                win.addch(5,2+i,' ',curses.color_pair(2))
            win.addstr(5,2,str(choices[itemindex])[0:msglen-6],curses.color_pair(2))
            win.addch(5,msglen-1,curses.ACS_DARROW)
            win.refresh()

#--------------- End of Reusable dialogs section ---------------

# New Scan window function
def newscan_win(options:ScanOptions):
    win = init_dialog(6,40,floor(curses.LINES / 2),floor(curses.COLS / 2 - 20),1,'New Scan')
    win.keypad(True)
    scan_modes = []
    focus = 0
    for item in ScanModes: #extracting just the names and putting on a list for the choice dialog 
        if item['root'] and current_uid != 0:
            continue
        scan_modes.append(item['name'])
    # Rendering the window
    win.addstr(1,2,'Target IPs:')
    win.addstr('None                ',curses.color_pair(4))
    win.addstr(2,2,' Scan Mode:')
    win.addstr(2,13,'                    ',curses.color_pair(4))
    win.addstr(2,13,scan_modes[options.mode],curses.color_pair(4))
    win.addstr(3,2,'[ Start Scanning ]',curses.color_pair(2))
    win.addstr(4,2,'[ Cancel ]',curses.color_pair(2))
    win.addch(1,1,'>',2)
    while True:
        keypressed = win.getch()
        if keypressed == curses.KEY_UP:
            if focus > 0: #if the focused "widget" is not the first one, we focus on the prior "widget"
                focus -= 1
                for i in range(4): #we update the cursor
                    if i == focus:
                        win.addch(1+i,1,'>',2)
                    else:
                        win.addch(1+i,1,' ')
                win.refresh()
            else:
                curses.beep() # beep if the up arrow key is pressed but we are on the first item
        elif keypressed == curses.KEY_DOWN:
            if focus < 3: #if the focused "widget" is not the last one, we focus on the next
                focus += 1
                for i in range(4): #we update the cursor
                    if i == focus:
                        win.addch(1+i,1,'>',2)
                    else:
                        win.addch(1+i,1,' ')
                win.refresh()
            else:
                curses.beep() # beep if the focused "widget" is the last one and the down key was pressed
        elif (keypressed == curses.KEY_ENTER) or (keypressed in [10,13]):
            if focus == 0: #IP Address field is focused
                options.ip_address = input_dialog('Target IPs','Insert the target IP or IP range.',options.ip_address,20)
                win.addstr(1,13,'                    ',curses.color_pair(4)) #fill with blank spaces
                if options.ip_address == '': #if the ip address is blank we print None
                    win.addstr(1,13,'None                ',curses.color_pair(4))
                else: #otherwise we print the target ip address   
                    win.addstr(1,13,options.ip_address,curses.color_pair(4)) #
                win.redrawwin()
                win.refresh()
            elif focus == 1:#Scan Mode field is focused
                options.mode = choice_dialog('Scan Mode','Select the scan mode',scan_modes)
                win.addstr(2,13,'                   ',curses.color_pair(4))
                win.addstr(2,13,scan_modes[options.mode],curses.color_pair(4))
                win.redrawwin()
                win.refresh()
            elif focus == 2:#Confirm "button" is focused
                del(win)
                return True
            elif focus == 4:#Cancel "button" is focused
                del(win)
                return False
        elif keypressed == curses.KEY_CANCEL:
            return False

def perform_scan(nm:nmap,mode:int, target:str):
    #Rendering the window
    try:
        scanning_window = init_dialog(4,30,floor(curses.LINES / 2 -2),floor(curses.COLS / 2 -15),3,'Scanning')
        scanning_window.addstr(1,3,"/!\\ Scan in progress /!\\",curses.A_BLINK)
        scanning_window.addstr(2,7,"Please wait...")
        scanning_window.refresh()
        nm.scan(target,arguments=ScanModes[mode]['param'],sudo=current_uid==0)
        del(scanning_window)
        return True
    except:
        error_dialog('Error scanning',f'cmdline:{nm.command_line()}')
        del(scanning_window)
        return False    
def main(arg):
    scan_opt = ScanOptions()
    nm = nmap.PortScanner()   
    stdscr = init_application()
    stdscr.timeout(10)
    #Rendering border
    stdscr.border(curses.ACS_VLINE,curses.ACS_VLINE,curses.ACS_HLINE,curses.ACS_HLINE,curses.ACS_ULCORNER,curses.ACS_URCORNER,curses.ACS_LLCORNER,curses.ACS_LRCORNER)
    stdscr.addstr(0,1,"[ Cursed nmap ]")
    #Rendering the toolbar 
    for i in range(curses.COLS-2):
        stdscr.addch(1,1+i,' ',curses.color_pair(2))
        stdscr.addch(2,1+i,curses.ACS_HLINE)
    stdscr.addstr(1,2,'[New Scan | Save Output | Quit]',curses.color_pair(2))
    stdscr.addch(1,3,'N',curses.color_pair(5))
    stdscr.addch(1,14,'S',curses.color_pair(5))
    stdscr.addch(1,28,'Q',curses.color_pair(5))
    #Rendering the Host List Rectangle
    rectangle(stdscr,3,1,curses.LINES-3,25)
    stdscr.addstr(3,2,'[Host List]')
    stdscr.addstr(curses.LINES -3,2,'             ',curses.color_pair(3))
    stdscr.addstr(curses.LINES -3,2,'0 of 0',curses.color_pair(3))
    #Rendering the Host Details Rectangle
    rectangle(stdscr,3,26,7,curses.COLS-3)
    stdscr.addstr(3,27,'[Host Detail]')
    stdscr.addstr(4,27,'Operating System:')
    stdscr.addstr(5,27,'IP Address:')
    stdscr.addstr(6,27,'Hostname:')
    #Render Port detail
    rectangle(stdscr,8,26,curses.LINES-3,curses.COLS-3)
    stdscr.addstr(8,27,'[Port Detail]')
    stdscr.addstr(curses.LINES-3,27,'             ',curses.color_pair(3))
    stdscr.addstr(curses.LINES-3,27,'0 of 0',curses.color_pair(3))
    #Render the status bar
    for i in range(curses.COLS-2):
        stdscr.addch(curses.LINES-2,1+i,' ',curses.color_pair(2))
    stdscr.addstr(curses.LINES-2,1,f'Cursed nmap version:{VERSION_STRING}',curses.color_pair(2))
    #Check if nmap is installed 
    try:
        subprocess.check_output(['whereis','nmap'])
    except:
        error_dialog('Critical Error','nmap binary not found, please install nmap and try again.')
        exit()
    #Check if we are root, and warn if we are not
    if current_uid != 0:
        error_dialog('Warning','Not running as root, this will limit your scan options!')
        stdscr.redrawwin()
        stdscr.refresh()
    stdscr.refresh()
    while(True):
        keypressed = stdscr.getch()
        if keypressed == ord('n'):
            if newscan_win(scan_opt):
                if not perform_scan(nm,scan_opt.mode,scan_opt.ip_address):
                    continue
                host_index = 0
                for host in nm.all_hosts():   
                    if  host_index < curses.LINES -6:
                        if host_index == 0:
                            stdscr.addstr(4+host_index,2,host,curses.color_pair(4))
                            stdscr.addstr(6,34,host)
                            stdscr.addstr(7,38,nm[host].hostname())
                            port_index = 0
                            for proto in nm[host].all_protocols():
                                lport = list(nm[host][proto])
                                lport.sort()
                                for port in lport:
                                    if port_index < curses.LINES -6:
                                        stdscr.addstr(9+port_index,27,f"{proto}/{port} state:{nm[host][proto][port]['state']}")
                                    port_index +=1
                        else:
                            stdscr.addstr(4+host_index,2,host)
                    host_index += 1
                stdscr.redrawwin()
                stdscr.refresh()
            else:
                error_dialog('New Scan','Scan Cancelled!')
        if keypressed == ord('s'):
            try:
                filename = input_dialog('Save Scan','Select where you want to save the output file',path.expanduser('~'),260)
                with open(filename,'w') as filp:
                    filp.write(nm.csv())
            except:
                error_dialog('Error','Error saving the file.')
        if keypressed == ord('q'):
            curses.endwin()
            break
    
if __name__== '__main__':
    curses.wrapper(main)