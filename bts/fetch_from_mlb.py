from datetime import date
import requests
import re
from xml.etree import ElementTree
from gamescout_db import db, cur

debug_flag = False
atbat_rows = []
pitch_rows = []


def commit_to_db(stmt, data):
   if debug_flag == False:
      cur.executemany(stmt, data)
      db.commit()


def commit_atbats(data):
   stmt = """
      INSERT INTO AtBats (
         ATBAT_NUM,
         PITCHER,
         BATTER,
         BALLS,
         STRIKES,
         OUTS,
         TIME,
         BATTER_LR,
         PITCHER_LR,
         HT_R,
         AT_R,
         BATTER_HEIGHT,
         EVENT,
         INNING,
         TEAM_AB,
         TEAM_PITCH
      )
      VALUES (
         %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s 
      )
    """

   commit_to_db(stmt, data) 
      

def commit_pitches(data):
   stmt = """
      INSERT INTO Pitches (
         DESCRIPTION,
         TIME,
         X,
         Y,
         ON_2B,
         START_SPEED,
         END_SPEED,
         TYPE,
         SZ_TOP,
         SZ_BOT,
         PFX_X,
         PFX_Z,
         PX,
         PZ,
         X0,
         Y0,
         Z0,
         VX0,
         VY0,
         VZ0,
         AX,
         AY,
         AZ,
         BREAK_Y,
         BREAK_ANGLE,
         BREAK_LENGTH,
         PITCH_TYPE,
         TYPE_CONF,
         ZONE,
         NASTY,
         SPIN_DIR,
         SPIN_RATE
      )
      VALUES (
         %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
         %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
      )
   """

   commit_to_db(stmt, data)


def commit_and_save(year, month, day):
   global atbat_rows
   global pitch_rows
  
   print("Committing AtBats") 
   commit_atbats(atbat_rows)
   atbat_rows = []

   print("Committing Pitches")
   commit_pitches(pitch_rows)
   pitch_rows = []

   print("Creating Checkpoint")
   f = open("checkpoint.txt", "w")
   f.write("{0},{1},{2}".format(year, month, day)) 
   f.close()
      

def load_checkpoint():
   try:
      f = open("checkpoint.txt", "r")
      date = f.read().split(",")
      f.close()

      # Year, Month, Day
      return (int(date[0]), int(date[1]), int(date[2]))
   except IOError:
      print("IOError")
      return (2011, 3, 28)


def main():
   ckp_year, ckp_month, ckp_day = load_checkpoint()

   for year in range(ckp_year, date.today().year + 1):
      
      start_month = 3 if year != ckp_year else ckp_month
      for month in range(start_month, 10): 

         start_day = 1 if year != ckp_year or month != ckp_month else ckp_day + 1
         for day in range(start_day, num_days_in(month)+1):
            url = 'http://gd.mlb.com/components/game/mlb/year_{y}/month_{m:02d}/day_{d:02d}/'.format(y=year, m=month, d=day)
            games_index = requests.get(url).text
            games = re.findall(r'> (gid.*mlb.*mlb.*)/</a>', games_index)
            for game_id in games:
               if month == 3 or (month == 4 and day < 10):
                  spring_check_url = "{url}{gid}/linescore.json".format(url=url, gid=game_id)
                  spring_check = requests.get(spring_check_url).text
                  if re.search(r'spring', spring_check):
                     continue
               innings_url = "{url}{gid}/inning/".format(url=url, gid=game_id)
               innings_index = requests.get(innings_url).text
               innings = re.findall(r'(inning_[0-9]+)', innings_index)
               for inning in innings:
                  inning_url = "{url}{inning}.xml".format(url=innings_url, inning=inning)
                  data = requests.get(inning_url)
                  xml = ElementTree.fromstring(data.content)
                  parse(xml)
            commit_and_save(year, month, day)

            print("{m}/{d}/{y} loaded.".format(d=day, m=month, y=year))

   print("Data fetch complete ! ! !")


def safe(d, key):
   return d[key] if key in d else None


def parse_atbat(ab, inning, half):
   _height = ab["b_height"].split("-")
   height = int(_height[0]) * 12 + int(_height[1])
   
   if half == "top":
      team_ab = inning["away_team"]
      team_pitch = inning["home_team"]
   else:
      team_ab = inning["home_team"]
      team_pitch = inning["away_team"]

   time = ab["start_tfs_zulu"].replace("T", " ").replace("Z", "")

   return (
      safe(ab, "num"), safe(ab, "pitcher"), safe(ab, "batter"), safe(ab, "b"),
      safe(ab, "s"), safe(ab, "o"), time, safe(ab, "stand"), safe(ab, "p_throws"),
      safe(ab, "home_team_runs"), safe(ab, "away_team_runs"), height, safe(ab, "event"),
      safe(inning, "num"), team_ab, team_pitch)


def parse_pitch(p):
   time = p["tfs_zulu"].replace("T", " ").replace("Z", "")
   on_2b = p["on_2b"] if "on_2b" in p else None

   return (
      safe(p, "des"), time, safe(p, "x"), safe(p, "y"), on_2b, safe(p, "start_speed"),
      safe(p, "end_speed"), safe(p, "pitch_type"), safe(p, "sz_top"), safe(p, "sz_bot"),
      safe(p, "pfx_x"), safe(p, "pfx_z"), safe(p, "px"), safe(p, "pz"), safe(p, "x0"), 
      safe(p, "y0"), safe(p, "z0"), safe(p, "vx0"), safe(p, "vy0"), safe(p, "vz0"),
      safe(p, "ax"), safe(p, "ay"), safe(p, "az"), safe(p, "break_y"), safe(p, "break_angle"),
      safe(p, "break_length"), safe(p, "pitch_type"), safe(p, "type_confidence"),
      safe(p, "zone"), safe(p, "nasty"), safe(p, "spin_dir"), safe(p, "spin_rate"))


def parse(inning):
   for half in inning:
      for ab in half.findall('atbat'):
         atbat = parse_atbat(ab.attrib, inning.attrib, half.tag)
         atbat_rows.append(atbat)

         for p in ab.findall('pitch'):
            pitch = parse_pitch(p.attrib)
            pitch_rows.append(pitch)

                  
def num_days_in(month):
   return {
      3: 31, 4: 30, 5: 31,
      6: 30, 7: 31, 8: 31,
      9: 30, 10: 31
   }[month]


if __name__ == '__main__':
   main()
