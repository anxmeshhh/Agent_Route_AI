"""
migrate_routing_refs.py — One-time migration: seed the 6 new routing reference
tables (ref_geocoords, ref_maritime_routes, ref_cost_rates, ref_delay_bands,
ref_chokepoint_intel, ref_maritime_alt_routes) into MySQL.

Run once:  python migrate_routing_refs.py
"""
import mysql.connector
import json
import os

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", 3306)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", "theanimesh2005"),
    database=os.getenv("MYSQL_DATABASE", "shipment_risk_db"),
    charset="utf8mb4",
)
cur = conn.cursor()

print("Creating tables if not exist...")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_geocoords (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name_key       VARCHAR(128) NOT NULL UNIQUE,
    display        VARCHAR(128) NOT NULL,
    lat            DECIMAL(9,6) NOT NULL,
    lon            DECIMAL(9,6) NOT NULL,
    coord_type     ENUM('city','port','airport','road_hub','chokepoint') NOT NULL DEFAULT 'city',
    iata_code      VARCHAR(4),
    snap_radius_km TINYINT UNSIGNED DEFAULT 35
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_maritime_routes (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    origin_region    VARCHAR(32) NOT NULL,
    dest_region      VARCHAR(32) NOT NULL,
    chokepoint_keys  JSON NOT NULL,
    UNIQUE KEY uq_mr (origin_region, dest_region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_cost_rates (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    transport_mode ENUM('road','air','sea') NOT NULL,
    cargo_type     VARCHAR(64) NOT NULL,
    daily_cost_usd INT UNSIGNED NOT NULL,
    cost_source    VARCHAR(64) DEFAULT 'Industry estimate',
    UNIQUE KEY uq_cr (transport_mode, cargo_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_delay_bands (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    risk_score_min      TINYINT UNSIGNED NOT NULL,
    risk_score_max      TINYINT UNSIGNED NOT NULL,
    delay_probability   DECIMAL(4,2) NOT NULL,
    expected_delay_days DECIMAL(4,1) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_chokepoint_intel (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    key_name     VARCHAR(32) NOT NULL UNIQUE,
    why_chosen   TEXT NOT NULL,
    saves        VARCHAR(128),
    risk_notes   VARCHAR(255),
    intel_source VARCHAR(64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ref_maritime_alt_routes (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    trigger_key      VARCHAR(32) NOT NULL UNIQUE,
    via_label        VARCHAR(64) NOT NULL,
    reason           TEXT,
    when_to_choose   TEXT,
    waypoints_json   JSON NOT NULL,
    km_per_day       SMALLINT UNSIGNED DEFAULT 550
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
conn.commit()
print("Tables created.")

# ─── ref_geocoords ────────────────────────────────────────────────
geocoords = [
    # (name_key, display, lat, lon, coord_type, iata_code, snap_radius_km)
    # Cities
    ("delhi","Delhi",28.6139,77.2090,"city",None,35),
    ("new delhi","New Delhi",28.6139,77.2090,"city",None,35),
    ("mumbai","Mumbai",19.0760,72.8777,"city",None,35),
    ("bombay","Mumbai",19.0760,72.8777,"city",None,35),
    ("bangalore","Bangalore",12.9716,77.5946,"city",None,35),
    ("bengaluru","Bangalore",12.9716,77.5946,"city",None,35),
    ("chennai","Chennai",13.0827,80.2707,"city",None,35),
    ("madras","Chennai",13.0827,80.2707,"city",None,35),
    ("kolkata","Kolkata",22.5726,88.3639,"city",None,35),
    ("calcutta","Kolkata",22.5726,88.3639,"city",None,35),
    ("hyderabad","Hyderabad",17.3850,78.4867,"city",None,35),
    ("secunderabad","Secunderabad",17.4399,78.4983,"city",None,35),
    ("pune","Pune",18.5204,73.8567,"city",None,35),
    ("ahmedabad","Ahmedabad",23.0225,72.5714,"city",None,35),
    ("jaipur","Jaipur",26.9124,75.7873,"city",None,35),
    ("lucknow","Lucknow",26.8467,80.9462,"city",None,35),
    ("nagpur","Nagpur",21.1458,79.0882,"city",None,35),
    ("coimbatore","Coimbatore",11.0168,76.9558,"city",None,35),
    ("kochi","Kochi",9.9312,76.2673,"city",None,35),
    ("cochin","Kochi",9.9312,76.2673,"city",None,35),
    ("trivandrum","Thiruvananthapuram",8.5241,76.9366,"city",None,35),
    ("thiruvananthapuram","Thiruvananthapuram",8.5241,76.9366,"city",None,35),
    ("kerala","Kerala (centroid)",10.8505,76.2711,"city",None,35),
    ("indore","Indore",22.7196,75.8577,"city",None,35),
    ("bhopal","Bhopal",23.2599,77.4126,"city",None,35),
    ("surat","Surat",21.1702,72.8311,"city",None,35),
    ("vadodara","Vadodara",22.3072,73.1812,"city",None,35),
    ("baroda","Vadodara",22.3072,73.1812,"city",None,35),
    ("patna","Patna",25.5941,85.1376,"city",None,35),
    ("bhubaneswar","Bhubaneswar",20.2961,85.8245,"city",None,35),
    ("visakhapatnam","Visakhapatnam",17.6868,83.2185,"city",None,35),
    ("vizag","Visakhapatnam",17.6868,83.2185,"city",None,35),
    ("madurai","Madurai",9.9252,78.1198,"city",None,35),
    ("amritsar","Amritsar",31.6340,74.8723,"city",None,35),
    ("chandigarh","Chandigarh",30.7333,76.7794,"city",None,35),
    ("jodhpur","Jodhpur",26.2389,73.0243,"city",None,35),
    ("agra","Agra",27.1767,78.0081,"city",None,35),
    ("varanasi","Varanasi",25.3176,82.9739,"city",None,35),
    ("guwahati","Guwahati",26.1445,91.7362,"city",None,35),
    ("raipur","Raipur",21.2514,81.6296,"city",None,35),
    ("ranchi","Ranchi",23.3441,85.3096,"city",None,35),
    ("dehradun","Dehradun",30.3165,78.0322,"city",None,35),
    ("vijayawada","Vijayawada",16.5062,80.6480,"city",None,35),
    ("mangalore","Mangalore",12.9141,74.8560,"city",None,35),
    ("mysore","Mysore",12.2958,76.6394,"city",None,35),
    ("mysuru","Mysore",12.2958,76.6394,"city",None,35),
    ("tiruchirappalli","Tiruchirappalli",10.7905,78.7047,"city",None,35),
    ("trichy","Tiruchirappalli",10.7905,78.7047,"city",None,35),
    ("nashik","Nashik",19.9975,73.7898,"city",None,35),
    ("aurangabad","Aurangabad",19.8762,75.3433,"city",None,35),
    ("ludhiana","Ludhiana",30.9010,75.8573,"city",None,35),
    ("thirupur","Thirupur",11.1085,77.3411,"city",None,35),
    ("hubli","Hubli",15.3647,75.1240,"city",None,35),
    ("belgaum","Belagavi",15.8497,74.4977,"city",None,35),
    ("belagavi","Belagavi",15.8497,74.4977,"city",None,35),
    ("nhava sheva","Nhava Sheva",18.9500,72.9500,"port",None,35),
    ("mundra","Mundra",22.8393,69.7212,"port",None,35),
    # Global ports & cities
    ("shanghai","Shanghai",31.2304,121.4737,"port",None,35),
    ("ningbo","Ningbo",29.8683,121.5440,"port",None,35),
    ("shenzhen","Shenzhen",22.5431,114.0579,"port",None,35),
    ("tianjin","Tianjin",39.3434,117.3616,"port",None,35),
    ("qingdao","Qingdao",36.0671,120.3826,"port",None,35),
    ("guangzhou","Guangzhou",23.1291,113.2644,"port",None,35),
    ("hong kong","Hong Kong",22.3193,114.1694,"port",None,35),
    ("busan","Busan",35.1796,129.0756,"port",None,35),
    ("tokyo","Tokyo",35.6762,139.6503,"city",None,35),
    ("osaka","Osaka",34.6937,135.5023,"city",None,35),
    ("rotterdam","Rotterdam",51.9225,4.4792,"port",None,35),
    ("hamburg","Hamburg",53.5753,10.0153,"port",None,35),
    ("antwerp","Antwerp",51.2608,4.3946,"port",None,35),
    ("felixstowe","Felixstowe",51.9554,1.3519,"port",None,35),
    ("barcelona","Barcelona",41.3874,2.1686,"port",None,35),
    ("genoa","Genoa",44.4056,8.9463,"port",None,35),
    ("marseille","Marseille",43.2965,5.3698,"city",None,35),
    ("piraeus","Piraeus",37.9475,23.6452,"port",None,35),
    ("le havre","Le Havre",49.4944,0.1079,"port",None,35),
    ("singapore","Singapore",1.3521,103.8198,"port",None,35),
    ("jebel ali","Jebel Ali",24.9857,55.0919,"port",None,35),
    ("dubai","Dubai",25.2048,55.2708,"city",None,35),
    ("abu dhabi","Abu Dhabi",24.4539,54.3773,"city",None,35),
    ("salalah","Salalah",17.0239,54.0924,"port",None,35),
    ("colombo","Colombo",6.9271,79.8612,"port",None,35),
    ("los angeles","Los Angeles",33.7701,-118.1937,"port",None,35),
    ("long beach","Long Beach",33.7701,-118.1937,"port",None,35),
    ("new york","New York",40.6643,-74.0000,"port",None,35),
    ("seattle","Seattle",47.6062,-122.3321,"city",None,35),
    ("houston","Houston",29.7604,-95.3698,"city",None,35),
    ("savannah","Savannah",32.0835,-81.0998,"port",None,35),
    ("santos","Santos",-23.9618,-46.3322,"port",None,35),
    ("callao","Callao",-12.0553,-77.1184,"port",None,35),
    ("durban","Durban",-29.8587,31.0218,"port",None,35),
    ("mombasa","Mombasa",-4.0435,39.6682,"port",None,35),
    ("lagos","Lagos",6.5244,3.3792,"city",None,35),
    ("dar es salaam","Dar es Salaam",-6.7924,39.2083,"port",None,35),
    ("sydney","Sydney",-33.8688,151.2093,"city",None,35),
    ("melbourne","Melbourne",-37.8136,144.9631,"city",None,35),
    ("london","London",51.5074,-0.1278,"city",None,35),
    ("paris","Paris",48.8566,2.3522,"city",None,35),
    ("berlin","Berlin",52.5200,13.4050,"city",None,35),
    ("madrid","Madrid",40.4168,-3.7038,"city",None,35),
    ("rome","Rome",41.9028,12.4964,"city",None,35),
    ("milan","Milan",45.4642,9.1900,"city",None,35),
    ("amsterdam","Amsterdam",52.3676,4.9041,"city",None,35),
    ("brussels","Brussels",50.8503,4.3517,"city",None,35),
    ("vienna","Vienna",48.2082,16.3738,"city",None,35),
    ("zurich","Zurich",47.3769,8.5417,"city",None,35),
    ("munich","Munich",48.1351,11.5820,"city",None,35),
    ("frankfurt","Frankfurt",50.1109,8.6821,"city",None,35),
    ("warsaw","Warsaw",52.2297,21.0122,"city",None,35),
    ("prague","Prague",50.0755,14.4378,"city",None,35),
    ("lisbon","Lisbon",38.7223,-9.1393,"city",None,35),
    ("athens","Athens",37.9838,23.7275,"city",None,35),
    ("istanbul","Istanbul",41.0082,28.9784,"city",None,35),
    ("copenhagen","Copenhagen",55.6761,12.5683,"city",None,35),
    ("stockholm","Stockholm",59.3293,18.0686,"city",None,35),
    ("oslo","Oslo",59.9139,10.7522,"city",None,35),
    ("helsinki","Helsinki",60.1699,24.9384,"city",None,35),
    ("budapest","Budapest",47.4979,19.0402,"city",None,35),
    ("bucharest","Bucharest",44.4268,26.1025,"city",None,35),
    ("lyon","Lyon",45.7640,4.8357,"city",None,35),
    ("chicago","Chicago",41.8781,-87.6298,"city",None,35),
    ("san francisco","San Francisco",37.7749,-122.4194,"city",None,35),
    ("miami","Miami",25.7617,-80.1918,"city",None,35),
    ("atlanta","Atlanta",33.7490,-84.3880,"city",None,35),
    ("dallas","Dallas",32.7767,-96.7970,"city",None,35),
    ("denver","Denver",39.7392,-104.9903,"city",None,35),
    ("toronto","Toronto",43.6532,-79.3832,"city",None,35),
    ("vancouver","Vancouver",49.2827,-123.1207,"city",None,35),
    ("montreal","Montreal",45.5017,-73.5673,"city",None,35),
    ("mexico city","Mexico City",19.4326,-99.1332,"city",None,35),
    ("bogota","Bogota",4.7110,-74.0721,"city",None,35),
    ("lima","Lima",-12.0464,-77.0428,"city",None,35),
    ("santiago","Santiago",-33.4489,-70.6693,"city",None,35),
    ("buenos aires","Buenos Aires",-34.6037,-58.3816,"city",None,35),
    ("rio de janeiro","Rio de Janeiro",-22.9068,-43.1729,"city",None,35),
    ("sao paulo","Sao Paulo",-23.5505,-46.6333,"city",None,35),
    ("cairo","Cairo",30.0444,31.2357,"city",None,35),
    ("nairobi","Nairobi",-1.2921,36.8219,"city",None,35),
    ("johannesburg","Johannesburg",-26.2041,28.0473,"city",None,35),
    ("cape town","Cape Town",-33.9249,18.4241,"city",None,35),
    ("casablanca","Casablanca",33.5731,-7.5898,"city",None,35),
    ("riyadh","Riyadh",24.7136,46.6753,"city",None,35),
    ("doha","Doha",25.2854,51.5310,"city",None,35),
    ("tehran","Tehran",35.6892,51.3890,"city",None,35),
    ("ankara","Ankara",39.9334,32.8597,"city",None,35),
    ("addis ababa","Addis Ababa",9.0320,38.7469,"city",None,35),
    ("accra","Accra",5.6037,-0.1870,"city",None,35),
    ("bangkok","Bangkok",13.7563,100.5018,"city",None,35),
    ("kuala lumpur","Kuala Lumpur",3.1390,101.6869,"city",None,35),
    ("jakarta","Jakarta",-6.2088,106.8456,"city",None,35),
    ("manila","Manila",14.5995,120.9842,"city",None,35),
    ("ho chi minh","Ho Chi Minh City",10.8231,106.6297,"city",None,35),
    ("hanoi","Hanoi",21.0285,105.8542,"city",None,35),
    ("seoul","Seoul",37.5665,126.9780,"city",None,35),
    ("beijing","Beijing",39.9042,116.4074,"city",None,35),
    ("taipei","Taipei",25.0330,121.5654,"city",None,35),
    ("brisbane","Brisbane",-27.4698,153.0251,"city",None,35),
    ("perth","Perth",-31.9505,115.8605,"city",None,35),
    ("auckland","Auckland",-36.8485,174.7633,"city",None,35),
    # Airports
    ("del -- indira gandhi intl","DEL - Indira Gandhi Intl",28.5562,77.1000,"airport","DEL",80),
    ("bom -- chhatrapati shivaji intl","BOM - Chhatrapati Shivaji Intl",19.0896,72.8656,"airport","BOM",80),
    ("blr -- kempegowda intl","BLR - Kempegowda Intl",13.1986,77.7066,"airport","BLR",80),
    ("maa -- chennai intl","MAA - Chennai Intl",12.9941,80.1709,"airport","MAA",80),
    ("ccu -- netaji subhas intl","CCU - Netaji Subhas Intl",22.6547,88.4467,"airport","CCU",80),
    ("hyd -- rajiv gandhi intl","HYD - Rajiv Gandhi Intl",17.2403,78.4294,"airport","HYD",80),
    ("cok -- cochin intl","COK - Cochin Intl",10.1520,76.4019,"airport","COK",80),
    ("amd -- sardar vallabhbhai intl","AMD - Sardar Vallabhbhai Intl",23.0770,72.6347,"airport","AMD",80),
    ("lhr -- heathrow","LHR - Heathrow",51.4775,-0.4614,"airport","LHR",80),
    ("cdg -- charles de gaulle","CDG - Charles de Gaulle",49.0097,2.5478,"airport","CDG",80),
    ("fra -- frankfurt","FRA - Frankfurt",50.0379,8.5622,"airport","FRA",80),
    ("ams -- schiphol","AMS - Schiphol",52.3086,4.7639,"airport","AMS",80),
    ("dxb -- dubai intl","DXB - Dubai Intl",25.2532,55.3657,"airport","DXB",80),
    ("sin -- changi","SIN - Changi",1.3644,103.9915,"airport","SIN",80),
    ("hkg -- hong kong intl","HKG - Hong Kong Intl",22.3080,113.9185,"airport","HKG",80),
    ("nrt -- tokyo narita","NRT - Tokyo Narita",35.7720,140.3929,"airport","NRT",80),
    ("jfk -- john f kennedy","JFK - John F Kennedy",40.6413,-73.7781,"airport","JFK",80),
    ("ord -- ohare","ORD - OHare",41.9742,-87.9073,"airport","ORD",80),
    ("lax -- los angeles intl","LAX - Los Angeles Intl",33.9425,-118.4081,"airport","LAX",80),
    ("syd -- kingsford smith","SYD - Kingsford Smith",-33.9399,151.1753,"airport","SYD",80),
    ("doh -- doha hamad intl","DOH - Doha Hamad Intl",25.2731,51.6080,"airport","DOH",80),
    ("ist -- istanbul intl","IST - Istanbul Intl",41.2753,28.7519,"airport","IST",80),
    ("icn -- incheon","ICN - Incheon",37.4602,126.4407,"airport","ICN",80),
    ("pek -- beijing capital","PEK - Beijing Capital",40.0799,116.6031,"airport","PEK",80),
    ("pvg -- shanghai pudong","PVG - Shanghai Pudong",31.1443,121.8083,"airport","PVG",80),
    ("kul -- klia","KUL - KLIA",2.7456,101.7100,"airport","KUL",80),
    ("gru -- sao paulo guarulhos","GRU - Sao Paulo Guarulhos",-23.4356,-46.4731,"airport","GRU",80),
    ("jnb -- or tambo","JNB - OR Tambo",-26.1367,28.2411,"airport","JNB",80),
    ("nbo -- nairobi jomo kenyatta","NBO - Nairobi Jomo Kenyatta",-1.3192,36.9275,"airport","NBO",80),
    # Chokepoints
    ("suez canal cp","Suez Canal",30.0,32.55,"chokepoint",None,5),
    ("bab el-mandeb cp","Bab el-Mandeb",12.65,43.30,"chokepoint",None,5),
    ("strait of gibraltar cp","Strait of Gibraltar",35.95,-5.45,"chokepoint",None,5),
    ("malacca strait cp","Malacca Strait",1.25,103.65,"chokepoint",None,5),
    ("strait of hormuz cp","Strait of Hormuz",26.56,56.25,"chokepoint",None,5),
    ("panama canal cp","Panama Canal",8.99,-79.57,"chokepoint",None,5),
    ("cape of good hope cp","Cape of Good Hope",-34.36,18.47,"chokepoint",None,5),
    ("dover strait cp","Dover Strait",51.11,1.35,"chokepoint",None,5),
    ("south china sea cp","South China Sea",12.0,114.0,"chokepoint",None,5),
    ("arabian sea cp","Arabian Sea",15.0,65.0,"chokepoint",None,5),
    ("eastern mediterranean cp","Eastern Mediterranean",34.0,25.0,"chokepoint",None,5),
    ("north pacific e cp","North Pacific E",35.0,150.0,"chokepoint",None,5),
    ("north pacific w cp","North Pacific W",35.0,-145.0,"chokepoint",None,5),
    ("north atlantic cp","North Atlantic",45.0,-30.0,"chokepoint",None,5),
    ("south atlantic cp","South Atlantic",-15.0,-25.0,"chokepoint",None,5),
    # Road hubs
    ("nagpur junction","Nagpur Junction",21.1458,79.0882,"road_hub",None,35),
    ("hyderabad hub","Hyderabad Hub",17.3850,78.4867,"road_hub",None,35),
    ("bengaluru hub","Bengaluru Hub",12.9716,77.5946,"road_hub",None,35),
    ("coimbatore, nh544","Coimbatore, NH544",11.0168,76.9558,"road_hub",None,35),
    ("kochi port","Kochi Port",9.9312,76.2673,"road_hub",None,35),
    ("pune junction","Pune Junction",18.5204,73.8567,"road_hub",None,35),
    ("jaipur hub","Jaipur Hub",26.9124,75.7873,"road_hub",None,35),
    ("ahmedabad hub","Ahmedabad Hub",23.0225,72.5714,"road_hub",None,35),
    ("lucknow hub","Lucknow Hub",26.8467,80.9462,"road_hub",None,35),
    ("surat hub","Surat Hub",21.1702,72.8311,"road_hub",None,35),
    ("vadodara hub","Vadodara Hub",22.3072,73.1812,"road_hub",None,35),
    ("bhopal junction","Bhopal Junction",23.2599,77.4126,"road_hub",None,35),
    ("indore hub","Indore Hub",22.7196,75.8577,"road_hub",None,35),
    ("visakhapatnam hub","Visakhapatnam Hub",17.6868,83.2185,"road_hub",None,35),
    ("bhubaneswar hub","Bhubaneswar Hub",20.2961,85.8245,"road_hub",None,35),
    ("chennai junction","Chennai Junction",13.0827,80.2707,"road_hub",None,35),
    ("kolkata hub","Kolkata Hub",22.5726,88.3639,"road_hub",None,35),
    ("patna hub","Patna Hub",25.5941,85.1376,"road_hub",None,35),
    ("varanasi junction","Varanasi Junction",25.3176,82.9739,"road_hub",None,35),
    ("agra hub","Agra Hub",27.1767,78.0081,"road_hub",None,35),
    ("chandigarh hub","Chandigarh Hub",30.7333,76.7794,"road_hub",None,35),
    ("amritsar hub","Amritsar Hub",31.6340,74.8723,"road_hub",None,35),
    ("madurai hub","Madurai Hub",9.9252,78.1198,"road_hub",None,35),
    ("mangalore hub","Mangalore Hub",12.9141,74.8560,"road_hub",None,35),
    ("mysuru hub","Mysuru Hub",12.2958,76.6394,"road_hub",None,35),
    ("nashik hub","Nashik Hub",19.9975,73.7898,"road_hub",None,35),
    ("hubli junction","Hubli Junction",15.3647,75.1240,"road_hub",None,35),
    ("vijayawada hub","Vijayawada Hub",16.5062,80.6480,"road_hub",None,35),
    ("guwahati hub","Guwahati Hub",26.1445,91.7362,"road_hub",None,35),
    ("ranchi hub","Ranchi Hub",23.3441,85.3096,"road_hub",None,35),
    ("jodhpur hub","Jodhpur Hub",26.2389,73.0243,"road_hub",None,35),
    ("karachi hub","Karachi Hub",24.8607,67.0011,"road_hub",None,35),
    ("lahore hub","Lahore Hub",31.5804,74.3587,"road_hub",None,35),
    ("islamabad hub","Islamabad Hub",33.7294,73.0931,"road_hub",None,35),
    ("colombo hub","Colombo Hub",6.9271,79.8612,"road_hub",None,35),
    ("dhaka hub","Dhaka Hub",23.8103,90.4125,"road_hub",None,35),
    ("kathmandu hub","Kathmandu Hub",27.7172,85.3240,"road_hub",None,35),
    ("bangkok hub","Bangkok Hub",13.7563,100.5018,"road_hub",None,35),
    ("kuala lumpur hub","Kuala Lumpur Hub",3.1390,101.6869,"road_hub",None,35),
    ("jakarta hub","Jakarta Hub",-6.2088,106.8456,"road_hub",None,35),
    ("phnom penh hub","Phnom Penh Hub",11.5564,104.9282,"road_hub",None,35),
    ("ho chi minh hub","Ho Chi Minh Hub",10.8231,106.6297,"road_hub",None,35),
    ("hanoi hub","Hanoi Hub",21.0285,105.8542,"road_hub",None,35),
    ("beijing hub","Beijing Hub",39.9042,116.4074,"road_hub",None,35),
    ("shanghai hub","Shanghai Hub",31.2304,121.4737,"road_hub",None,35),
    ("guangzhou hub","Guangzhou Hub",23.1291,113.2644,"road_hub",None,35),
    ("chengdu hub","Chengdu Hub",30.5728,104.0668,"road_hub",None,35),
    ("wuhan hub","Wuhan Hub",30.5928,114.3055,"road_hub",None,35),
    ("xian hub","Xian Hub",34.3416,108.9398,"road_hub",None,35),
    ("tokyo hub","Tokyo Hub",35.6762,139.6503,"road_hub",None,35),
    ("osaka hub","Osaka Hub",34.6937,135.5023,"road_hub",None,35),
    ("seoul hub","Seoul Hub",37.5665,126.9780,"road_hub",None,35),
    ("paris hub","Paris Hub",48.8566,2.3522,"road_hub",None,35),
    ("berlin hub","Berlin Hub",52.5200,13.4050,"road_hub",None,35),
    ("frankfurt hub","Frankfurt Hub",50.1109,8.6821,"road_hub",None,35),
    ("munich hub","Munich Hub",48.1351,11.5820,"road_hub",None,35),
    ("hamburg hub","Hamburg Hub",53.5753,10.0153,"road_hub",None,35),
    ("london hub","London Hub",51.5074,-0.1278,"road_hub",None,35),
    ("amsterdam hub","Amsterdam Hub",52.3676,4.9041,"road_hub",None,35),
    ("brussels hub","Brussels Hub",50.8503,4.3517,"road_hub",None,35),
    ("milan hub","Milan Hub",45.4642,9.1900,"road_hub",None,35),
    ("rome hub","Rome Hub",41.9028,12.4964,"road_hub",None,35),
    ("madrid hub","Madrid Hub",40.4168,-3.7038,"road_hub",None,35),
    ("barcelona hub","Barcelona Hub",41.3874,2.1686,"road_hub",None,35),
    ("vienna hub","Vienna Hub",48.2082,16.3738,"road_hub",None,35),
    ("warsaw hub","Warsaw Hub",52.2297,21.0122,"road_hub",None,35),
    ("prague hub","Prague Hub",50.0755,14.4378,"road_hub",None,35),
    ("zurich hub","Zurich Hub",47.3769,8.5417,"road_hub",None,35),
    ("lyon hub","Lyon Hub",45.7640,4.8357,"road_hub",None,35),
    ("marseille hub","Marseille Hub",43.2965,5.3698,"road_hub",None,35),
    ("stockholm hub","Stockholm Hub",59.3293,18.0686,"road_hub",None,35),
    ("copenhagen hub","Copenhagen Hub",55.6761,12.5683,"road_hub",None,35),
    ("helsinki hub","Helsinki Hub",60.1699,24.9384,"road_hub",None,35),
    ("oslo hub","Oslo Hub",59.9139,10.7522,"road_hub",None,35),
    ("athens hub","Athens Hub",37.9838,23.7275,"road_hub",None,35),
    ("istanbul hub","Istanbul Hub",41.0082,28.9784,"road_hub",None,35),
    ("bucharest hub","Bucharest Hub",44.4268,26.1025,"road_hub",None,35),
    ("budapest hub","Budapest Hub",47.4979,19.0402,"road_hub",None,35),
    ("dubai hub","Dubai Hub",25.2048,55.2708,"road_hub",None,35),
    ("riyadh hub","Riyadh Hub",24.7136,46.6753,"road_hub",None,35),
    ("tehran hub","Tehran Hub",35.6892,51.3890,"road_hub",None,35),
    ("ankara hub","Ankara Hub",39.9334,32.8597,"road_hub",None,35),
    ("cairo hub","Cairo Hub",30.0444,31.2357,"road_hub",None,35),
    ("casablanca hub","Casablanca Hub",33.5731,-7.5898,"road_hub",None,35),
    ("nairobi hub","Nairobi Hub",-1.2921,36.8219,"road_hub",None,35),
    ("addis ababa hub","Addis Ababa Hub",9.0320,38.7469,"road_hub",None,35),
    ("lagos hub","Lagos Hub",6.5244,3.3792,"road_hub",None,35),
    ("accra hub","Accra Hub",5.6037,-0.1870,"road_hub",None,35),
    ("johannesburg hub","Johannesburg Hub",-26.2041,28.0473,"road_hub",None,35),
    ("cape town hub","Cape Town Hub",-33.9249,18.4241,"road_hub",None,35),
    ("dar es salaam hub","Dar es Salaam Hub",-6.7924,39.2083,"road_hub",None,35),
    ("new york hub","New York Hub",40.7128,-74.0060,"road_hub",None,35),
    ("los angeles hub","Los Angeles Hub",34.0522,-118.2437,"road_hub",None,35),
    ("chicago hub","Chicago Hub",41.8781,-87.6298,"road_hub",None,35),
    ("houston hub","Houston Hub",29.7604,-95.3698,"road_hub",None,35),
    ("miami hub","Miami Hub",25.7617,-80.1918,"road_hub",None,35),
    ("atlanta hub","Atlanta Hub",33.7490,-84.3880,"road_hub",None,35),
    ("dallas hub","Dallas Hub",32.7767,-96.7970,"road_hub",None,35),
    ("toronto hub","Toronto Hub",43.6532,-79.3832,"road_hub",None,35),
    ("montreal hub","Montreal Hub",45.5017,-73.5673,"road_hub",None,35),
    ("mexico city hub","Mexico City Hub",19.4326,-99.1332,"road_hub",None,35),
    ("sao paulo hub","Sao Paulo Hub",-23.5505,-46.6333,"road_hub",None,35),
    ("rio de janeiro hub","Rio de Janeiro Hub",-22.9068,-43.1729,"road_hub",None,35),
    ("buenos aires hub","Buenos Aires Hub",-34.6037,-58.3816,"road_hub",None,35),
    ("santiago hub","Santiago Hub",-33.4489,-70.6693,"road_hub",None,35),
    ("bogota hub","Bogota Hub",4.7110,-74.0721,"road_hub",None,35),
    ("lima hub","Lima Hub",-12.0464,-77.0428,"road_hub",None,35),
    ("sydney hub","Sydney Hub",-33.8688,151.2093,"road_hub",None,35),
    ("melbourne hub","Melbourne Hub",-37.8136,144.9631,"road_hub",None,35),
    ("brisbane hub","Brisbane Hub",-27.4698,153.0251,"road_hub",None,35),
    ("perth hub","Perth Hub",-31.9505,115.8605,"road_hub",None,35),
    ("auckland hub","Auckland Hub",-36.8485,174.7633,"road_hub",None,35),
]

print(f"Inserting {len(geocoords)} geocoords...")
cur.executemany(
    "INSERT IGNORE INTO ref_geocoords (name_key,display,lat,lon,coord_type,iata_code,snap_radius_km) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
    geocoords
)

# ─── ref_maritime_routes ───────────────────────────────────────────
maritime_routes = [
    ("east_asia","europe",json.dumps(["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"])),
    ("east_asia","middle_east",json.dumps(["south china sea cp","malacca strait cp","arabian sea cp","strait of hormuz cp"])),
    ("east_asia","indian_ocean",json.dumps(["south china sea cp","malacca strait cp"])),
    ("east_asia","us_west",json.dumps(["north pacific e cp","north pacific w cp"])),
    ("east_asia","us_east",json.dumps(["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp","north atlantic cp"])),
    ("east_asia","africa",json.dumps(["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp"])),
    ("east_asia","south_america",json.dumps(["north pacific e cp","north pacific w cp","panama canal cp"])),
    ("east_asia","oceania",json.dumps(["south china sea cp"])),
    ("indian_ocean","europe",json.dumps(["arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"])),
    ("indian_ocean","middle_east",json.dumps(["arabian sea cp","strait of hormuz cp"])),
    ("indian_ocean","us_east",json.dumps(["arabian sea cp","bab el-mandeb cp","suez canal cp","strait of gibraltar cp","north atlantic cp"])),
    ("indian_ocean","africa",json.dumps(["arabian sea cp","bab el-mandeb cp"])),
    ("indian_ocean","east_asia",json.dumps(["malacca strait cp","south china sea cp"])),
    ("europe","us_east",json.dumps(["dover strait cp","north atlantic cp"])),
    ("europe","us_west",json.dumps(["strait of gibraltar cp","panama canal cp"])),
    ("europe","south_america",json.dumps(["strait of gibraltar cp","south atlantic cp"])),
    ("europe","middle_east",json.dumps(["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","strait of hormuz cp"])),
    ("europe","africa",json.dumps(["strait of gibraltar cp"])),
    ("europe","indian_ocean",json.dumps(["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","arabian sea cp"])),
    ("europe","oceania",json.dumps(["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","arabian sea cp","malacca strait cp","south china sea cp"])),
    ("middle_east","europe",json.dumps(["strait of hormuz cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"])),
    ("middle_east","us_east",json.dumps(["strait of hormuz cp","bab el-mandeb cp","suez canal cp","strait of gibraltar cp","north atlantic cp"])),
    ("middle_east","africa",json.dumps(["strait of hormuz cp","bab el-mandeb cp"])),
    ("middle_east","east_asia",json.dumps(["strait of hormuz cp","arabian sea cp","malacca strait cp","south china sea cp"])),
    ("middle_east","indian_ocean",json.dumps(["strait of hormuz cp","arabian sea cp"])),
    ("us_east","south_america",json.dumps(["south atlantic cp"])),
    ("us_west","south_america",json.dumps(["panama canal cp"])),
    ("us_west","east_asia",json.dumps(["north pacific w cp","north pacific e cp"])),
    ("us_east","europe",json.dumps(["north atlantic cp","dover strait cp"])),
    ("africa","south_america",json.dumps(["cape of good hope cp","south atlantic cp"])),
    ("africa","europe",json.dumps(["strait of gibraltar cp"])),
    ("africa","east_asia",json.dumps(["bab el-mandeb cp","arabian sea cp","malacca strait cp","south china sea cp"])),
    ("africa","indian_ocean",json.dumps(["bab el-mandeb cp","arabian sea cp"])),
]

print(f"Inserting {len(maritime_routes)} maritime routes...")
cur.executemany(
    "INSERT IGNORE INTO ref_maritime_routes (origin_region,dest_region,chokepoint_keys) VALUES (%s,%s,%s)",
    maritime_routes
)

# ─── ref_cost_rates ────────────────────────────────────────────────
cost_rates = [
    ("road","electronics",2000,"IRU 2024 road freight rates"),
    ("road","perishables",2500,"IRU 2024 road freight rates"),
    ("road","automotive",1800,"IRU 2024 road freight rates"),
    ("road","chemicals",2200,"IRU 2024 road freight rates"),
    ("road","pharmaceutical",2800,"IRU 2024 road freight rates"),
    ("road","pharmaceuticals",2800,"IRU 2024 road freight rates"),
    ("road","general",1200,"IRU 2024 road freight rates"),
    ("road","bulk",1000,"IRU 2024 road freight rates"),
    ("road","energy",3000,"IRU 2024 road freight rates"),
    ("air","electronics",12000,"IATA 2024 air cargo rates"),
    ("air","perishables",15000,"IATA 2024 air cargo rates"),
    ("air","automotive",8000,"IATA 2024 air cargo rates"),
    ("air","chemicals",10000,"IATA 2024 air cargo rates"),
    ("air","pharmaceutical",18000,"IATA 2024 air cargo rates"),
    ("air","pharmaceuticals",18000,"IATA 2024 air cargo rates"),
    ("air","general",6000,"IATA 2024 air cargo rates"),
    ("air","bulk",5000,"IATA 2024 air cargo rates"),
    ("air","energy",8000,"IATA 2024 air cargo rates"),
    ("sea","electronics",85000,"BIMCO 2024 charter rates"),
    ("sea","perishables",72000,"BIMCO 2024 charter rates"),
    ("sea","automotive",68000,"BIMCO 2024 charter rates"),
    ("sea","chemicals",75000,"BIMCO 2024 charter rates"),
    ("sea","pharmaceutical",90000,"BIMCO 2024 charter rates"),
    ("sea","pharmaceuticals",90000,"BIMCO 2024 charter rates"),
    ("sea","general",55000,"BIMCO 2024 charter rates"),
    ("sea","bulk",28000,"BIMCO 2024 charter rates"),
    ("sea","energy",110000,"BIMCO 2024 charter rates"),
]
print(f"Inserting {len(cost_rates)} cost rates...")
cur.executemany(
    "INSERT IGNORE INTO ref_cost_rates (transport_mode,cargo_type,daily_cost_usd,cost_source) VALUES (%s,%s,%s,%s)",
    cost_rates
)

# ─── ref_delay_bands ───────────────────────────────────────────────
# Check if already has data to avoid duplicates
cur.execute("SELECT COUNT(*) FROM ref_delay_bands")
if cur.fetchone()[0] == 0:
    cur.executemany(
        "INSERT INTO ref_delay_bands (risk_score_min,risk_score_max,delay_probability,expected_delay_days) VALUES (%s,%s,%s,%s)",
        [(80,100,0.82,4.5),(65,79,0.65,3.1),(45,64,0.42,1.8),(25,44,0.22,0.9),(0,24,0.10,0.3)]
    )
    print("Inserted 5 delay bands.")
else:
    print("Delay bands already seeded, skipping.")

# ─── ref_chokepoint_intel ──────────────────────────────────────────
intel = [
    ("suez","Shortest Asia-Europe corridor — avoids 6,000nm Cape of Good Hope detour","12-15 transit days","Canal congestion, Houthi threat in Red Sea approach","IMO maritime advisory"),
    ("malacca","Shortest Pacific-Indian Ocean passage — 40% of world trade flows here","4-6 transit days vs Lombok Strait","Piracy hotspot, extreme traffic density","ReCAAP ISC"),
    ("gibraltar","Only viable Atlantic-Mediterranean entry without circumnavigating Africa","10,000+ nm vs Cape route","Strong currents, dense traffic","EMSA routing guidance"),
    ("hormuz","Only maritime exit from Persian Gulf — mandatory for Gulf-origin cargo","No alternative — geography-locked","Geopolitical tension, military activity","UKMTO advisory"),
    ("panama","Pacific-Atlantic shortcut — eliminates Cape Horn rounding","8,000nm and 15+ days","Lock capacity limits, drought water-level restrictions","ACP canal authority"),
    ("cape","Selected because Suez route is higher risk or blocked","Avoids Suez congestion/security risk","Rough seas, +12 days transit time, higher fuel cost","SA maritime authority"),
    ("bab","Mandatory Red Sea approach for Suez-bound vessels","No alternative for Suez access","Security corridor, Houthi threat zone","UKMTO advisory"),
    ("dover","North Sea-English Channel link — busiest shipping lane globally","Direct access to NW European ports","Extreme traffic density, fog risk","MCA Dover TSS"),
]
print(f"Inserting {len(intel)} chokepoint intel entries...")
cur.executemany(
    "INSERT IGNORE INTO ref_chokepoint_intel (key_name,why_chosen,saves,risk_notes,intel_source) VALUES (%s,%s,%s,%s,%s)",
    intel
)

# ─── ref_maritime_alt_routes ───────────────────────────────────────
alt_routes = [
    ("suez","Cape of Good Hope",
     "Avoids Red Sea/Suez corridor — eliminates geopolitical risk (Houthi threat, canal congestion)",
     "Choose when Red Sea security is elevated or Suez Canal has queue delays > 48 hours.",
     json.dumps([{"lat":-6.0,"lon":71.0,"name":"Indian Ocean (South)"},{"lat":-34.3568,"lon":18.4740,"name":"Cape of Good Hope"},{"lat":-15.0,"lon":-5.0,"name":"South Atlantic"},{"lat":10.0,"lon":-20.0,"name":"Central Atlantic"}]),
     550),
    ("bab","Cape of Good Hope",
     "Avoids Red Sea/Bab el-Mandeb threat zone — Cape of Good Hope diversion",
     "Choose when Red Sea security is elevated or Suez Canal has queue delays > 48 hours.",
     json.dumps([{"lat":-6.0,"lon":71.0,"name":"Indian Ocean (South)"},{"lat":-34.3568,"lon":18.4740,"name":"Cape of Good Hope"},{"lat":-15.0,"lon":-5.0,"name":"South Atlantic"},{"lat":10.0,"lon":-20.0,"name":"Central Atlantic"}]),
     550),
    ("panama","Cape Horn Route",
     "Avoids Panama Canal — eliminates lock queue delays and draft restrictions",
     "Choose when Panama Canal has drought restrictions or lock queue > 7 days.",
     json.dumps([{"lat":-20.0,"lon":-70.0,"name":"South Pacific"},{"lat":-55.98,"lon":-67.27,"name":"Cape Horn"},{"lat":-35.0,"lon":-50.0,"name":"South Atlantic"}]),
     550),
    ("malacca","Lombok Strait (Indonesia)",
     "Avoids Malacca congestion — routes through Lombok Strait (deeper draft, less traffic)",
     "Choose when Malacca has piracy alerts or extreme traffic density.",
     json.dumps([{"lat":-8.4,"lon":115.7,"name":"Lombok Strait"},{"lat":-8.0,"lon":80.0,"name":"Indian Ocean"}]),
     550),
]
print(f"Inserting {len(alt_routes)} maritime alt routes...")
cur.executemany(
    "INSERT IGNORE INTO ref_maritime_alt_routes (trigger_key,via_label,reason,when_to_choose,waypoints_json,km_per_day) VALUES (%s,%s,%s,%s,%s,%s)",
    alt_routes
)

conn.commit()
cur.close()
conn.close()

print("\n✅ Migration complete!")
print("Rows inserted:")
print("  ref_geocoords     →", len(geocoords))
print("  ref_maritime_routes →", len(maritime_routes))
print("  ref_cost_rates    →", len(cost_rates))
print("  ref_delay_bands   → 5")
print("  ref_chokepoint_intel →", len(intel))
print("  ref_maritime_alt_routes →", len(alt_routes))
