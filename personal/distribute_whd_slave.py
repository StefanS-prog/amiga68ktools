import os,sys,subprocess,shutil,glob,colorama,re
colorama.init()
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("slave_dev_dir", nargs='+',help="slave development dir")
parser.add_argument("-s","--say-sorry", help="sent wrong old slave with same version",
                    action="store_true")
parser.add_argument("-t","--test-mode", help="send to me",
                    action="store_true")
args = parser.parse_args()

tmparc = []
progdir = os.path.dirname(__file__)

full_chain_mode = False
temp = r"K:\jff\AmigaHD\Download\whdload"
# if full_chain_mode else os.getenv("TEMP")

c = colorama.Fore.LIGHTGREEN_EX

# create addresses to avoid spammers to grep addresses from github
def makeaddress(f,d):
    return "{}@{}".format(f,d)



try:

    for devdir in args.slave_dev_dir: # r"C:\DATA\jff\AmigaHD\PROJETS\HDInstall\DONE\D\DataStormHDDev"
        tmpdir = os.path.join(temp,os.path.basename(devdir)[:-5]+"Install")
        usrdir = os.path.join(devdir,"usr")

        gamename = os.path.basename(devdir)[:-5]
        print("Building {}...".format(gamename))
        output = subprocess.check_output("build.bat",shell=True,stdin=subprocess.DEVNULL,cwd=devdir)
        print(output.decode("ascii",errors="ignore"))
        print("Copying to user archive...")
        for slave in glob.glob(os.path.join(devdir,"*.slave")):
            with open(slave,"rb") as f:
                contents = f.read()
                if b"DEBUG MODE" in contents or b"CHIP MODE" in contents:
                    raise Exception("Cannot distribute a 'DEBUG/CHIP MODE' slave")


            shutil.copy(slave,usrdir)
        for slave in glob.glob(os.path.join(devdir,"*.islave")):
            shutil.copy(slave,usrdir)
        for s in ["src","source"]:
            sd = os.path.join(usrdir,s)
            if os.path.isdir(sd):
                break
        else:
            os.mkdir(sd)

        with open(os.path.join(usrdir,"readme")) as f:
            contents = f.read()
            version_info = sorted(re.findall("^\s*[Vv]ersion\s+(\d+\.\d+)",contents,flags=re.M),key=lambda x:[int(z) for z in re.findall("\d+",x)])[-1]


        for src in glob.glob(os.path.join(devdir,"*.s")):
            with open(src) as f:
                f = list(f)
                fi = iter(f)
                for line in fi:
                    if "DECL_VERSION" in line:
                        version = re.findall(r'\s+dc\.b\s+"(\d+\.\d+)"',next(fi))[0]
                        print("{} version {}, readme version {}".format(src,version,version_info))
                        break
                else:
                    print("{} unknown version".format(src))
                for line in f:
                    if "blitz" in line:
                        raise Exception("blitz macro found in {}".format(src))
            shutil.copy(src,sd)
        print("Creating archive, make sure that WinUAE is running and unpaused...")
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        shutil.copytree(usrdir,tmpdir)
        arcname = gamename+".lha"
        arcfile = os.path.join(temp,arcname)
        if os.path.exists(arcfile):
            os.remove(arcfile)
        uaefs = os.path.join(tmpdir,"_UAEFSDB.___")
        if os.path.exists(uaefs):
            os.remove(uaefs)

        if full_chain_mode:
            pass
        else:
            shell_name = "amigash"
            temp_shell = os.path.join(os.getenv("TEMP"),shell_name)
            with open(temp_shell,"wb") as f:
                f.write("""cd DOWNLOAD:whdload\nlha a -r "{0}.lha" "{0}Install"\n""".format(gamename).encode())
            subprocess.check_output(["squirt","localhost",temp_shell])
            subprocess.check_output(["squirt_exec","localhost","execute","T:"+shell_name])
            if os.path.exists(arcfile):
                print("{} created on the amiga side!!".format(arcfile))
    if not full_chain_mode:
        # send by e-mail

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email.utils import COMMASPACE, formatdate
        from email import encoders

        import smtplib
        fromaddr = makeaddress('jotd666','gmail.com')
        toaddrs  = [makeaddress('release','whdload.de')]
        if args.test_mode:
            toaddrs = [fromaddr]
        msg = MIMEMultipart()
        msg['From'] = fromaddr
        msg['To'] = COMMASPACE.join(toaddrs)
        msg['Date'] = formatdate(localtime=True)
        subject = "slave update for {}".format(gamename)
        if args.say_sorry:
            subject += " (sorry, re-sending, ignore previous)"
        msg['Subject'] = subject
        msg.attach( MIMEText("Enjoy!\n\nJFF\n") )
        print(subject)
        for file in [arcfile]:
            part = MIMEBase('application', "octet-stream")
            part.set_payload( open(file,"rb").read() )
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"'
                           % os.path.basename(file))
            msg.attach(part)

        print("Sending e-mail to {}...".format(toaddrs))
        username = fromaddr
        with open(os.path.join(os.getenv("USERPROFILE"),"password.txt")) as f:
            password = f.read().strip()

        server = smtplib.SMTP('smtp.gmail.com:587')
        server.ehlo()
        server.starttls()
        server.login(username,password)
        server.sendmail(fromaddr, toaddrs, msg.as_string())
        server.quit()
        print("Done.")
except Exception as e:
    c = colorama.Fore.LIGHTRED_EX
    print("Error: {}{}{}".format(c,e,colorama.Fore.RESET))

print("{}Press a key to exit{}".format(c,colorama.Fore.RESET))
input()