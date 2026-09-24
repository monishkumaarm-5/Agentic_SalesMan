-- =====================================================================
-- Add customer_feedback column to the products table and populate with
-- realistic customer feedback for each product.
--
-- Usage:
--   mysql -u <username> -p retail_shop < sql/seed/02_customer_feedback.sql
--
-- The backend re-indexes automatically on its next start.
-- =====================================================================

-- MySQL 8 has no `ADD COLUMN IF NOT EXISTS` (a MariaDB extension), so
-- check information_schema first; safe to re-run.
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'products' AND COLUMN_NAME = 'customer_feedback'
);
SET @ddl := IF(@exists = 0, 'ALTER TABLE products ADD COLUMN customer_feedback TEXT NULL AFTER description', 'DO 0');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Also fix the Trein Nova 12 Lite description to clarify the branding
UPDATE products SET description = 'Trein store-brand smartphone (powered by Samsung internals). A reliable everyday phone with a big battery and a smooth 90Hz display.'
WHERE name = 'Trein Nova 12 Lite';

-- ─── Mobile ──────────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Great battery life, lasts 2 full days on moderate use | Camera is decent for the price, night mode could be better | The 90Hz display is smooth for scrolling | Fingerprint sensor is fast and reliable | Value for money, does everything I need for daily tasks | Heats up slightly during heavy gaming sessions | Call quality is crystal clear | Fast charging works well, 0-50% in 30 mins | Build quality feels premium for this price range | OS updates have been consistent so far'
WHERE name = 'Trein Nova 12 Lite';

UPDATE products SET customer_feedback = 'The 6000mAh battery is incredible, easily lasts 2 days | AMOLED display colors are vivid and accurate | 5G connectivity is future-proof at this price | Slight lag when switching between heavy apps | Camera performance in daylight is excellent | Night mode photos are impressive for a mid-ranger | Gaming performance is smooth for casual games | One UI is feature-rich but takes time to learn | Good audio quality through speakers | Fast charging could be faster for this battery size'
WHERE name = 'Galaxy M35 5G';

UPDATE products SET customer_feedback = 'Best value phone in this range, 256GB storage is generous | 108MP camera takes stunning photos in good light | Fast charging is genuinely fast, 0-100% in 45 mins | AMOLED screen quality rivals phones twice the price | MIUI has too many pre-installed apps | Battery life is good, easily gets through a full day | Fingerprint unlock is snappy | Build quality is solid with Gorilla Glass | Gaming on this processor is surprisingly smooth | Customer service response was quick when needed'
WHERE name = 'Redmi Note 14';

UPDATE products SET customer_feedback = 'OxygenOS is the cleanest Android experience | Processor is blazing fast for this price segment | Fast charging is phenomenal, full charge in under an hour | Build quality and feel in hand is premium | Camera is good but not class-leading in low light | Display is bright and crisp outdoors | No expandable storage is a minor disappointment | Smooth performance even with 20+ apps open | Great for multitasking and heavy usage | Sound quality through speakers is above average'
WHERE name = 'OnePlus Nord CE 5';

UPDATE products SET customer_feedback = 'The Dynamic Island is genuinely useful after a week | Camera quality is outstanding, especially portrait mode | iOS ecosystem integration with Mac/iPad is seamless | Battery life improved significantly over previous model | Build quality and finish are top-notch | Face ID works perfectly in all lighting conditions | Performance is buttery smooth for everything | Speakers are loud and clear for video calls | Worth the premium for the longevity of iOS updates | Storage options should start at 256GB for this price'
WHERE name = 'iPhone 15';

UPDATE products SET customer_feedback = 'Google AI features are genuinely useful in daily life | Camera is the best in this price range, period | Software updates come first and are always smooth | Stock Android experience is clean and fast | Battery life is decent but not class-leading | Build quality feels premium and durable | Night Sight camera mode is unmatched | Call screening feature is incredibly useful | Display is bright with excellent color accuracy | Heating is minimal even during extended use'
WHERE name = 'Pixel 9';

UPDATE products SET customer_feedback = 'Unbeatable value for money in this segment | Battery backup is excellent for the price | Display quality is surprisingly good | Camera is adequate for social media photos | Realme UI has improved a lot, fewer bloatware now | Fast charging at this price is a great bonus | Build quality is decent, feels sturdy | Good for students and first-time smartphone users | Performance handles daily tasks without issues | Sound quality is average, not the strongest point'
WHERE name = 'Realme Narzo 70x';

UPDATE products SET customer_feedback = 'The titanium frame is gorgeous and extremely durable | ProRes video recording is a game-changer for creators | Action Button is more useful than I expected | Camera zoom quality at 5x is mind-blowing | Battery easily lasts a full day of heavy use | The best display on any smartphone, period | Performance handles anything you throw at it | Weight is noticeable but you get used to it | USB-C finally, about time | Worth every rupee for power users and creators'
WHERE name = 'iPhone 15 Pro Max';

-- ─── Laptop ──────────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Great gaming laptop for the price, RTX handles most titles | Fan noise is acceptable during gaming, quiet during work | Display could be brighter for outdoor use | Keyboard is comfortable for long typing sessions | Build quality is solid for a budget gaming laptop | Battery lasts about 4 hours for office work | Boots up fast with the SSD | Heat management is decent with the dual-fan setup | Good port selection including USB-C | Lenovo Vantage software is useful for performance tuning'
WHERE name = 'Lenovo LOQ 15';

UPDATE products SET customer_feedback = 'Perfect for students and office work | Lightweight and easy to carry around | Display is decent but not the brightest | Battery life is good, around 6-7 hours | Keyboard and touchpad are comfortable | HP support service was helpful | Runs Office apps and browsing smoothly | Design looks professional and sleek | SSD makes everything load fast | Fan noise is minimal during light tasks'
WHERE name = 'HP Pavilion 15';

UPDATE products SET customer_feedback = 'Stunning display with razor-thin bezels | Build quality is exceptional, all-metal chassis | Keyboard has excellent key travel for a thin laptop | Battery lasts a full workday easily | Extremely light and portable | Speakers are surprisingly good for the size | Performance is snappy for coding and multitasking | Touchpad is the best on any Windows laptop | Expensive but you get what you pay for | Thunderbolt 4 ports are versatile'
WHERE name = 'Dell XPS 13';

UPDATE products SET customer_feedback = 'Best budget laptop for everyday computing | Display is bright and good for content consumption | Battery life is around 5-6 hours | Keyboard is comfortable for long typing sessions | Lightweight and easy to carry for college | Performance handles Chrome with many tabs well | Value for money is hard to beat | Plastic build feels okay for the price | Fan can get loud under sustained load | Good for students and basic office work'
WHERE name = 'ASUS Vivobook 15';

UPDATE products SET customer_feedback = 'M3 chip performance is incredible for creative work | Battery life is genuinely all-day, 15+ hours | Fanless design means zero noise | Display quality and color accuracy are stunning | Best trackpad on any laptop by far | macOS is smooth and well-optimized | Super lightweight for traveling | Speakers sound amazing for a laptop this thin | Worth every rupee for professionals | Limited to 2 external displays without workaround'
WHERE name = 'MacBook Air M3';

UPDATE products SET customer_feedback = 'Good gaming performance at an affordable price | Display has a nice 144Hz refresh rate | Battery life is short under gaming, about 3 hours | Keyboard backlight is useful for night gaming | Build quality is decent for the price | Runs most games at medium-high settings | Gets warm but thermals are manageable | Good port selection for peripherals | Weight is fine for occasional carrying | Acer customer service could be better'
WHERE name = 'Acer Aspire 7';

UPDATE products SET customer_feedback = 'Best business laptop keyboard, hands down | Build quality is rugged and professional | Battery lasts a full workday with ease | Security features like fingerprint reader are reliable | Display is decent for productivity work | Trackpoint is great once you get used to it | Lightweight for a business-class laptop | Runs demanding business applications smoothly | Great Linux compatibility | Camera and mic quality are good for video calls'
WHERE name = 'Lenovo ThinkPad E14';

UPDATE products SET customer_feedback = 'Powerful gaming performance, handles AAA titles | Display with 165Hz is smooth for competitive gaming | Thermal management keeps temps in check | RGB keyboard is customizable and looks great | Build quality is sturdy and premium | Battery life is poor for non-gaming use, about 3 hours | Fan noise is quite loud during gaming | HP Omen Gaming Hub is useful for tuning | Good speaker quality for a gaming laptop | Heavy but expected for this level of performance'
WHERE name = 'HP Omen 16';

-- ─── Headphone ────────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Incredible bass for the price, boAt never disappoints | Battery lasts around 8 hours with ANC on | Fit is comfortable for extended wear | ANC blocks out most office and commute noise | Microphone quality is good for calls | Touch controls are responsive and intuitive | Charging case is compact and easy to carry | Sound leaks slightly at high volumes | IPX5 rating handled my gym sessions well | Best TWS under 3000 rupees without question'
WHERE name = 'Trein Beat Buds Pro';

UPDATE products SET customer_feedback = 'Ultra lightweight, you forget you are wearing them | Sound quality is balanced with good mids | Battery life is impressive for the size | ANC is present but basic, blocks mild noise | Comfortable for long work-from-home sessions | Call quality is clear in quiet environments | App customization options are decent | Build quality feels durable | Quick charge feature is handy | Good value for money in the TWS segment'
WHERE name = 'Noise Buds Aero';

UPDATE products SET customer_feedback = 'Best ANC in the market, nothing comes close | Sound quality is audiophile-grade across all genres | Comfort for all-day wear is unmatched | 30-hour battery life is not an exaggeration | Multipoint connection between devices works perfectly | Build quality is premium and durable | Touch controls are precise and reliable | Speak-to-Chat feature is surprisingly useful | Folds flat for easy storage when traveling | Worth the premium price for serious music lovers'
WHERE name = 'Sony WH-1000XM5';

UPDATE products SET customer_feedback = 'Great sound quality for the price, JBL signature bass | ANC is effective for daily commuting | Comfortable padding for extended wear | Battery lasts around 35 hours without ANC | Foldable design is convenient for storage | Microphone is decent for video calls | Bluetooth range is stable up to 10 meters | Slightly heavy for long listening sessions | App equalizer offers good customization | Solid build quality, feels like a premium product'
WHERE name = 'JBL Tune 760NC';

UPDATE products SET customer_feedback = 'Seamless integration with Apple devices is magical | Spatial Audio is an immersive experience | ANC is top-tier, blocks out airplane noise | Fit is comfortable and secure for workouts | Sound quality is rich and detailed | Transparency mode sounds completely natural | MagSafe charging case is convenient | Battery life is solid at around 6 hours | Conversation Awareness is genuinely useful | The best earbuds if you are in the Apple ecosystem'
WHERE name = 'Apple AirPods Pro 2';

UPDATE products SET customer_feedback = 'Amazing bass response at an incredibly low price | Comfortable over-ear design for long sessions | Battery lasts over 20 hours easily | Bluetooth connection is stable and quick to pair | Build quality is decent for the price point | Sound quality is good for casual listening | Soft ear cushions are a nice touch | Foldable design makes it easy to carry | Microphone works well for calls | Best headphone under 2000 rupees'
WHERE name = 'boAt Rockerz 550';

UPDATE products SET customer_feedback = 'Audiophile-level sound quality in every genre | ANC adapts perfectly to different environments | Build quality is exceptional with premium materials | 60-hour battery life is absolutely insane | Comfort is outstanding for all-day wear | Touch controls are smooth and responsive | Microphone quality is crystal clear for calls | Sound Personalization feature is a game-changer | Folds beautifully into a slim case | Expensive but worth every rupee for music enthusiasts'
WHERE name = 'Sennheiser Momentum 4';

UPDATE products SET customer_feedback = 'Good sound quality for the price with clear mids | IP55 rating handles rain and sweat easily | Battery lasts around 7 hours with ANC | Lightweight and comfortable for daily commute | ANC is decent for this price range | Quick pairing with OnePlus phones is seamless | Case is compact and well-designed | Call quality is good in moderate noise | Bass is punchy without overwhelming | Solid option in the mid-range TWS segment'
WHERE name = 'OnePlus Buds 3';

-- ─── Television ──────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Great smart TV features with PatchWall OS | Picture quality is impressive for the price | Sound is decent but a soundbar would help | Remote control with Google Assistant is convenient | HDR content looks noticeably better | Boot time is quick after recent updates | WiFi connectivity is stable for streaming | Good selection of pre-installed apps | Wall mount installation was easy | Best value 43-inch smart TV available'
WHERE name = 'Trein Vision 43 Smart';

UPDATE products SET customer_feedback = 'Crystal 4K display is sharp and vibrant | 50-inch screen is perfect for our living room | Samsung Tizen OS is smooth and responsive | Dolby Digital Plus audio is immersive | Smart features work well with SmartThings | HDR10+ makes a visible difference | Remote with voice control is handy | Picture quality improves with AI upscaling | Slim design looks elegant on the wall | Streaming apps load quickly without lag'
WHERE name = 'Samsung Crystal 4K 50';

UPDATE products SET customer_feedback = 'AI ThinQ integration with smart home is excellent | webOS is the best smart TV OS by far | Picture quality with AI processing is stunning | Magic Remote pointer navigation is unique and intuitive | 55-inch size is ideal for a medium room | Dolby Atmos and Vision support enhance content | Low input lag makes it good for casual gaming | Design is modern and minimalist | Wide viewing angles for family watching | App store has all major streaming services'
WHERE name = 'LG UHD AI ThinQ 55';

UPDATE products SET customer_feedback = 'Sony picture processing is in a league of its own | Triluminos display produces incredibly natural colors | Google TV interface is well-organized | Sound quality is good with built-in speakers | 55-inch screen immersive for movies | Dolby Vision and Atmos combination is fantastic | Remote is simple and functional | Android TV app selection is extensive | Motion handling is smooth for sports | Worth the premium for picture quality alone'
WHERE name = 'Sony Bravia X75L 55';

UPDATE products SET customer_feedback = 'Best budget 32-inch TV for a bedroom or kitchen | Smart features work well for the price | YouTube and Netflix load without issues | Sound is basic, good for a small room | Picture quality is clear for HD content | Remote is simple and easy to use | Slim design fits well in tight spaces | Power consumption is low | WiFi connectivity is reliable | Perfect for a second TV in the house'
WHERE name = 'OnePlus TV Y1S 32';

UPDATE products SET customer_feedback = 'QLED display offers stunning colors and contrast | 65-inch screen is cinematic for movie nights | Google TV has a great content recommendation engine | Dolby Vision HDR makes everything look better | Sound quality is good but a soundbar enhances it | Gaming mode with low lag is a nice bonus | Design is slim and premium looking | Smart home integration works smoothly | Price-to-size ratio is unbeatable | Remote with voice search is convenient'
WHERE name = 'TCL QLED 65';

UPDATE products SET customer_feedback = 'Neo QLED display is breathtaking, deep blacks | One Connect box keeps the setup clean | Tizen OS is the fastest smart TV platform | 65-inch is perfect for a large living room | Dolby Atmos surround from built-in speakers is impressive | Gaming at 120Hz is smooth for PS5 and Xbox | Solar-powered remote is an eco-friendly touch | AI upscaling improves even lower quality content | Premium build quality all around | The best TV Samsung makes, worth the investment'
WHERE name = 'Samsung Neo QLED 65';

UPDATE products SET customer_feedback = 'Affordable 40-inch option for a mid-size room | Android TV with Google Play Store is versatile | Picture quality is good for the price | Sound quality is acceptable for daily viewing | Quick and easy to set up out of the box | Built-in Chromecast is useful | Remote design is minimal and clean | Power consumption is efficient | WiFi streaming is stable | Good choice for a basic smart TV need'
WHERE name = 'Mi 5A 40';

-- ─── Refrigerator ────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Frost-free operation means no manual defrosting | 260L capacity is perfect for a family of 3-4 | Energy efficient, low electricity bills | Smart Inverter Compressor is very quiet | Cooling is even across all shelves | Vegetable crisper keeps things fresh for longer | Build quality feels solid and durable | Door shelves are spacious for bottles | Ice maker works quickly | Good value for a double-door fridge'
WHERE name = 'Trein Frost Free 260L';

UPDATE products SET customer_feedback = 'Digital Inverter technology saves power noticeably | 236L is good for a small to medium family | Runs quietly even at night | Stabilizer-free operation is a money saver | Coolpack technology keeps food fresh during power cuts | Build quality is excellent for the price | Interior lighting is bright and helpful | Easy to clean shelves and compartments | Delivery and installation were smooth | Good brand reliability and after-sales service'
WHERE name = 'Samsung Digital Inverter 236L';

UPDATE products SET customer_feedback = 'Perfect single-door fridge for a small family or couple | IceMagic feature gives ice quickly | 190L is adequate for 2-3 people | Energy efficient with 4-star rating | Compact design fits well in small kitchens | Runs very quietly | Stabilizer-free operation is convenient | Shelves are adjustable and easy to clean | Toughened glass shelves feel sturdy | Whirlpool service center response was quick'
WHERE name = 'Whirlpool IceMagic 190L';

UPDATE products SET customer_feedback = 'Bottom mount design is ergonomic, less bending | 345L capacity is generous for a family of 4-5 | Energy efficient with inverter technology | Cooling performance is excellent throughout | Spacious vegetable drawer at eye level | Build quality feels premium | Runs quietly compared to older models | Convertible storage is a flexible feature | Installation team was professional | Haier service is responsive and reliable'
WHERE name = 'Haier Bottom Mount 345L';

UPDATE products SET customer_feedback = 'Massive 655L capacity is perfect for a large family | Side-by-side design gives easy access to everything | Water and ice dispenser on the door is convenient | Energy efficient despite the large size | Smart Diagnosis feature helped troubleshoot once | Interior lighting is bright LED | Runs surprisingly quiet for its size | Door alarm reminds you when left open | Premium look elevates the kitchen | Worth the investment for a big household'
WHERE name = 'LG Side-by-Side 655L';

UPDATE products SET customer_feedback = 'Compact 221L fits well in a small kitchen | Eon series quality is reliable as expected from Godrej | Energy efficient with consistent cooling | Vegetable tray keeps produce fresh for days | Runs quietly in our bedroom kitchen setup | Build quality is good for the price | Toughened glass shelves are easy to clean | Stabilizer-free operation is a plus | Good after-sales service from Godrej | Ideal for couples or bachelors'
WHERE name = 'Godrej Eon 221L';

UPDATE products SET customer_feedback = 'Family Hub touchscreen is futuristic and useful | 580L is spacious enough for anything | Can see inside the fridge from the phone app | Bixby integration controls the fridge by voice | Food management feature reduces waste | Energy consumption is reasonable for the features | Premium build quality and finish | Ice maker produces ice quickly | Expensive but the smart features justify it | Delivery and setup were handled professionally'
WHERE name = 'Samsung Family Hub 580L';

UPDATE products SET customer_feedback = 'Good 300L capacity for a mid-size family | 3-star rating keeps electricity bills reasonable | Frost-free operation works reliably | Cooling is consistent across compartments | Interior space is well-organized | Adjustable shelves help accommodate large items | Runs quietly in an open kitchen | Build quality is dependable Whirlpool standard | Good value in the mid-range segment | Service network is extensive across cities'
WHERE name = 'Whirlpool 300L 3 Star';

-- ─── Washing Machine ─────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Spin cycle cleans thoroughly for the price | 7kg capacity is perfect for a small family | Smart Inverter motor is energy efficient | Low noise even during the spin cycle | Multiple wash programs cover every fabric type | Tub clean feature keeps the drum hygienic | Easy to operate digital controls | Build quality is solid | Installation was quick and professional | Great value in the fully automatic segment'
WHERE name = 'Trein Spin Clean 7kg';

UPDATE products SET customer_feedback = 'EcoBubble technology cleans well even in cold water | Energy efficient and saves on electricity | 7kg handles weekly laundry for our family of 4 | Digital Inverter motor is whisper quiet | Multiple wash cycles for different fabrics | Drum clean notification is handy | Build quality is Samsung premium | Touch controls are responsive | Delivery and installation were smooth | Good after-sales support'
WHERE name = 'Samsung EcoBubble 7kg';

UPDATE products SET customer_feedback = 'Stainwash feature removes tough stains effectively | 6.5kg is good for a small family or couple | Low power consumption noticed on electricity bill | Wash quality is thorough and consistent | Simple and intuitive controls | Runs with less water usage | Build quality is standard Whirlpool reliable | Quiet operation is appreciated | Affordable and does the job well | Service technician came promptly when needed'
WHERE name = 'Whirlpool Stainwash 6.5kg';

UPDATE products SET customer_feedback = 'Best front-load washer in this price range | 8kg capacity handles large loads including blankets | IFB build quality and engineering are top-class | Aqua Energie treatment enhances detergent efficiency | Multiple wash programs for every fabric type | Steam wash feature removes tough stains | Cradle Wash is gentle on delicate clothes | Drum is stainless steel and durable | Energy and water efficient | After-sales service is excellent and responsive'
WHERE name = 'IFB Senator 8kg';

UPDATE products SET customer_feedback = 'German engineering quality is evident | 7kg front load handles weekly laundry easily | AntiVibration design means less noise and movement | EcoSilence Drive motor is impressively quiet | VarioPerfect saves energy or time as needed | Build quality feels built to last | Multiple temperature settings for different fabrics | Reload function lets you add forgotten items | Compact size fits well in smaller spaces | Bosch service network is reliable'
WHERE name = 'Bosch Series 4 7kg';

UPDATE products SET customer_feedback = 'Reliable top-load washer for daily laundry | 6.5kg handles our family of 3 comfortably | Smart Diagnosis feature helped troubleshoot once | Low noise motor is great for an apartment | Turbo Drum provides effective washing | Energy efficient with good star rating | Controls are simple and user-friendly | Build quality is LG dependable | Affordable and practical choice | Good after-sales support from LG service center'
WHERE name = 'LG Top Load 6.5kg';

UPDATE products SET customer_feedback = 'Budget-friendly semi-auto for basic washing needs | 8kg capacity is generous for the price | Wash and spin tubs work effectively | Good for families with heavy daily laundry | Simple operation, no complex controls | Saves water compared to hand washing | Compact enough for a utility area | Build quality is acceptable for the price | Requires manual effort to move clothes between tubs | Good entry-level option for budget-conscious buyers'
WHERE name = 'Haier Semi-Automatic 8kg';

UPDATE products SET customer_feedback = 'AI Control optimizes wash cycles automatically | 9kg front load handles everything including comforters | EcoBubble cleans effectively in cold water | Digital Inverter motor is energy efficient and quiet | Steam sanitize kills 99.9% bacteria | Build quality is excellent | WiFi connectivity to monitor from phone is handy | Drum is large and well-designed | Premium looking design elevates the laundry area | Samsung support was helpful for installation'
WHERE name = 'Samsung Front Load 9kg';

-- ─── Air Conditioner ─────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Cools the room quickly even in peak summer | 1.5 Ton is perfect for a medium bedroom | Energy efficient with good star rating | Runs quietly at night on sleep mode | Easy to clean filters | Remote control range is adequate | Build quality is standard and reliable | Installation team was professional | Copper condenser is durable | Good value for money in the AC segment'
WHERE name = 'Trein Cool Breeze 1.5 Ton';

UPDATE products SET customer_feedback = 'Precision cooling reaches the set temperature fast | 1 Ton is ideal for a small room or study | 5-star energy rating keeps bills very low | Dust filter is effective for allergy sufferers | Anti-corrosion coating extends outdoor unit life | Turbo mode cools rapidly when coming home | Sleep mode temperature management is smooth | Blue Star service is responsive | Build quality feels robust | Quiet operation even at full speed'
WHERE name = 'Blue Star 1 Ton';

UPDATE products SET customer_feedback = 'Dual inverter compressor saves noticeably on power | 1.5 Ton cools our 180 sq ft bedroom perfectly | 5-star rating reflected in lower electricity bills | Extremely quiet operation, barely audible at night | HD filter with anti-virus protection is useful | Ocean Black Fin protects outdoor unit from corrosion | WiFi control through LG ThinQ app is convenient | Cooling is consistent and comfortable | Premium build quality | Best inverter AC I have owned'
WHERE name = 'LG Dual Inverter 1.5 Ton';

UPDATE products SET customer_feedback = 'Japanese engineering quality is evident | 2 Ton cools our large living room effectively | Energy efficient even at higher tonnage | Coanda airflow distributes air evenly | Streamer technology purifies the air | Extremely reliable, running for 3 summers now | Quiet operation even at full capacity | Build quality of indoor and outdoor units is premium | Daikin service is professional and punctual | Worth the premium for a large room AC'
WHERE name = 'Daikin 2 Ton';

UPDATE products SET customer_feedback = 'WindFree cooling feels natural, no cold drafts | 1.5 Ton handles our bedroom efficiently | AI Auto mode adjusts automatically and saves energy | Runs quietly with the digital inverter | WiFi control through SmartThings app | Triple Protector Plus safeguards the compressor | Easy to clean filter panel | Modern design looks sleek on the wall | Samsung after-sales service is reliable | Comfortable cooling without the wind chill effect'
WHERE name = 'Samsung Windfree 1.5 Ton';

UPDATE products SET customer_feedback = 'Window AC is simple to install, no separate outdoor unit | 1.5 Ton cooling is effective for a standard room | Lower upfront cost compared to splits | Good for rental homes where split AC is not feasible | Runs reliably season after season | Slightly noisier than split ACs but manageable | Energy consumption is reasonable | Simple controls are easy for everyone | Voltas brand is trusted for ACs | Good value for the price point'
WHERE name = 'Voltas Window AC 1.5 Ton';

UPDATE products SET customer_feedback = 'Frost Wash feature self-cleans the indoor unit | 1.5 Ton is ideal for a standard bedroom | Tropical inverter technology handles extreme heat well | Copper condenser ensures long life | Energy efficient with low electricity bills | Cooling is fast and reaches all corners | Quiet enough for night use | Hitachi build quality is dependable | Remote control is simple and functional | Good brand reputation for ACs in India'
WHERE name = 'Hitachi 1.5 Ton';

UPDATE products SET customer_feedback = 'Nanoe-G air purification is noticeable in air quality | 1 Ton is perfect for our 120 sq ft room | Energy efficient with econavi sensor | Runs quietly on low and medium modes | Powerful mode cools down a hot room quickly | Dry mode is useful during monsoon season | Build quality is Panasonic reliable | Filter cleaning is straightforward | Compact indoor unit design | Good for small rooms and studies'
WHERE name = 'Panasonic 1 Ton';

-- ─── Microwave Oven ──────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Quick heating is genuinely fast for reheating meals | 20L capacity is good for a small family | Simple and intuitive controls | Auto-cook menus save time on common dishes | Even heating across the turntable | Easy to clean interior coating | Compact size fits well on the kitchen counter | Timer function is reliable | Good for basic reheating and defrosting | Affordable and does the job well'
WHERE name = 'Trein QuickCook 20L';

UPDATE products SET customer_feedback = 'Convection mode bakes beautifully, made perfect cakes | 28L is spacious for large dishes and baking trays | SlimFry feature makes healthier fried snacks | Ceramic enamel interior is easy to clean | Pre-programmed recipes are helpful for beginners | Power level control gives good flexibility | Even browning in convection mode | Touch panel is responsive and modern | Samsung quality build throughout | Great all-in-one oven for a modern kitchen'
WHERE name = 'Samsung Convection 28L';

UPDATE products SET customer_feedback = 'Grill function makes excellent kebabs and tikkas | 20L is adequate for daily reheating and grilling | Quartz heater grills faster than conventional | Easy to operate rotary controls | Intellowave technology ensures even cooking | Compact design fits small kitchen spaces | Anti-bacterial coating keeps interior hygienic | Auto-defrost is convenient for frozen items | Good brand reliability from LG | Affordable grill microwave option'
WHERE name = 'LG Grill 20L';

UPDATE products SET customer_feedback = 'Convection mode is great for baking and roasting | 25L capacity handles most family cooking needs | 3D heating system cooks evenly from all sides | Multi-stage cooking saves time | Crisp function makes excellent pizzas | Steam cooking option is healthy and convenient | Touch controls are modern and responsive | Interior is easy to clean | Whirlpool reliability is consistent | Good mid-range convection microwave'
WHERE name = 'Whirlpool Convection 25L';

UPDATE products SET customer_feedback = 'Best solo microwave for the price, does basics well | 17L is enough for reheating and simple cooking | Simple mechanical controls are easy for everyone | Compact and lightweight, fits anywhere | Power levels give good control | Timer is accurate and reliable | Easy to clean inside | Good for hostel students and bachelors | Bajaj brand is trusted and affordable | Does exactly what a basic microwave should'
WHERE name = 'Bajaj Solo 17L';

UPDATE products SET customer_feedback = 'IFB convection quality is outstanding for baking | 30L is the largest in our selection, great for families | Multi-stage cooking handles complex recipes | Starter kit with starter dough fermentation is unique | Deodorizer keeps the interior fresh | Stainless steel cavity is durable and hygienic | Touch and dial controls are intuitive | Even heat distribution for consistent results | Auto-cook menus cover Indian recipes well | Premium microwave for serious home cooking'
WHERE name = 'IFB Convection 30L';

UPDATE products SET customer_feedback = 'Grill combo mode is good for quick gratins | 23L is a good size for a mid-sized family | Auto-cook menus include common Indian dishes | Quartz grill heats up faster | Easy to operate mechanical knobs | Interior is easy to wipe clean | Panasonic quality feels durable | Defrost function is quick and even | Compact enough for a crowded kitchen | Good value in the grill microwave segment'
WHERE name = 'Panasonic Grill 23L';

UPDATE products SET customer_feedback = 'Simple and affordable solo microwave | 19L is good for 1-2 person households | Mechanical controls are straightforward | Heats food evenly and quickly | Compact and does not take much counter space | Timer and power controls work reliably | Easy to maintain and clean | Godrej brand offers good after-sales support | Low power consumption | Perfect for basic daily reheating needs'
WHERE name = 'Godrej Solo 19L';

-- ─── Smartwatch ──────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Large display is bright and easy to read outdoors | Tracks steps, heart rate and SpO2 accurately | Battery lasts about 5 days on normal use | Multiple sport modes cover most activities | Sleep tracking data is insightful | Notification display from phone is reliable | Comfortable silicone strap for all-day wear | Water resistant, used it while washing hands | Budget-friendly with good feature set | App interface is clean and intuitive'
WHERE name = 'Trein Pulse Fit';

UPDATE products SET customer_feedback = 'Stylish design looks good for the price | 1.69 inch display is clear and responsive | Battery lasts about 7 days | Heart rate and SpO2 monitoring work well | 100+ watch faces give nice variety | IP68 water resistance is practical | Bluetooth calling feature is useful | Notification alerts are reliable | boAt app is simple to navigate | Best smartwatch under 2000 rupees'
WHERE name = 'boAt Wave Neo';

UPDATE products SET customer_feedback = 'Best value Apple Watch for the ecosystem | Health tracking with heart rate and crash detection | Seamless pairing with iPhone is instant | Workout tracking is accurate and motivating | Battery lasts about a day and a half | Display is clear and bright | watchOS apps are well-designed | Water resistant for swimming | Notifications and calls on the wrist are convenient | Great entry point into Apple Watch lineup'
WHERE name = 'Apple Watch SE';

UPDATE products SET customer_feedback = 'Best Android smartwatch available | BioActive sensor health tracking is comprehensive | Wear OS with Samsung One UI is smooth and feature-rich | Battery lasts about 40 hours | GPS tracking is accurate for runs and walks | Always-on display is bright and legible | Samsung Pay for contactless payments is handy | Build quality with sapphire crystal is premium | Sleep Coaching feature is genuinely helpful | Pairs beautifully with Samsung Galaxy phones'
WHERE name = 'Samsung Galaxy Watch 7';

UPDATE products SET customer_feedback = 'AMOLED display is gorgeous at this price | Battery lasts an impressive 8 days | GPS accuracy is reliable for outdoor activities | Alexa integration is a nice smart feature | Blood oxygen and stress monitoring work well | 150+ sport modes cover every activity | Water resistance tested in the pool | Lightweight and comfortable for daily wear | Zepp app provides detailed health insights | Excellent value in the mid-range smartwatch segment'
WHERE name = 'Amazfit GTS 4';

UPDATE products SET customer_feedback = 'Best budget smartwatch with Bluetooth calling | Large round display looks great | Battery lasts about 6 days | Heart rate and SpO2 tracking are decent | Over 100 sport modes available | Built-in games are a fun addition | Rotating crown is easy to navigate | Water resistant for everyday use | Multiple watch faces to choose from | Incredible value under 2500 rupees'
WHERE name = 'Fire-Boltt Phoenix';

UPDATE products SET customer_feedback = 'Best fitness-focused smartwatch money can buy | GPS accuracy is unmatched for running and cycling | AMOLED display is bright and beautiful | Battery lasts 5 days with heavy fitness use | Body Battery and stress tracking are insightful | Training readiness score helps plan workouts | Music storage with offline Spotify is great | Build quality with titanium bezel is premium | Garmin Connect app is the most detailed fitness app | Worth the investment for serious fitness enthusiasts'
WHERE name = 'Garmin Venu 3';

UPDATE products SET customer_feedback = 'Dual-frequency GPS is accurate for outdoor tracking | AMOLED display is vibrant and responsive | Battery lasts about 48 hours with typical use | Wear OS gives access to Google Play apps | Health monitoring features are comprehensive | Build quality is solid with aluminum frame | Fast pairing with OnePlus phones | Comfortable to wear all day and night | Sleep tracking provides useful data | Good premium smartwatch at a competitive price'
WHERE name = 'OnePlus Watch 2';

-- ─── Tablet ──────────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Great for watching videos and casual browsing | 10-inch display is the right size for content | Battery lasts a full day of mixed use | Runs educational apps smoothly for kids | Good for note-taking with a stylus | Lightweight and easy to carry | Build quality is decent for the price | Speakers provide reasonable stereo sound | WiFi connectivity is stable | Best budget tablet for families'
WHERE name = 'Trein Slate 10';

UPDATE products SET customer_feedback = 'Good for media consumption and light productivity | Display quality is clear with vibrant colors | Battery life is excellent for a mid-range tablet | Samsung ecosystem integration with phone is useful | DeX mode adds a desktop-like experience | Multitasking with split screen works well | Camera is adequate for video calls | Build quality feels sturdy | One UI for tablets is well-optimized | Solid mid-range tablet choice'
WHERE name = 'Samsung Galaxy Tab A9+';

UPDATE products SET customer_feedback = 'Best tablet for its price, A14 chip is fast | Display quality is excellent for reading and videos | Battery lasts a full day easily | iPadOS app ecosystem is unmatched | Apple Pencil support is great for students | Keyboard Folio turns it into a laptop | Lightweight and portable | Speakers sound fantastic | Smooth performance for any task | The default recommendation for most people'
WHERE name = 'Apple iPad 10th Gen';

UPDATE products SET customer_feedback = 'Snapdragon 870 makes it surprisingly powerful | 11-inch display with 144Hz is super smooth | Quad speakers with Dolby Atmos sound amazing | Battery lasts 2 days with mixed use | Great for gaming with high refresh rate | Stylus support for note-taking | Build quality is metal and premium | MIUI Pad is clean and functional | Fast charging fills up quickly | Best value premium tablet'
WHERE name = 'Xiaomi Pad 6';

UPDATE products SET customer_feedback = 'Good display for movies and reading at the price | Battery lasts comfortably through a full day | Dolby Atmos speakers are a nice touch | Performance handles productivity apps well | Lightweight for carrying in a bag | Kids mode is useful for parents | Good for entertainment and light work | Lenovo build quality is reliable | WiFi range is decent | Affordable tablet with no major compromises'
WHERE name = 'Lenovo Tab P11';

UPDATE products SET customer_feedback = 'M2 chip turns this into a real work machine | Liquid Retina display is stunning for creative work | Apple Pencil Pro support is precise and responsive | Battery lasts a full workday | Laptop-grade performance in a tablet form | Stage Manager multitasking is game-changing | Speakers are among the best on any tablet | Lightweight yet powerful | Face ID unlock is seamless | The best tablet for professionals and creatives'
WHERE name = 'iPad Air M2';

UPDATE products SET customer_feedback = 'Affordable tablet for basic entertainment needs | Display is adequate for streaming and reading | Battery life is good for daily use | Lightweight and comfortable to hold | Good for kids educational content | Camera is basic but works for video calls | Runs common apps without issues | Build quality is acceptable for the price | Speaker quality is decent for personal use | Best entry-level tablet option'
WHERE name = 'Realme Pad 2';

UPDATE products SET customer_feedback = 'Premium AMOLED display is gorgeous for media | S Pen included is great for note-taking and art | Performance handles anything including split-screen | Battery life is solid for all-day use | Samsung DeX provides a full desktop experience | Quad speakers are rich and immersive | Build quality is flagship-level | Camera is the best on any tablet | IP68 water resistance is a standout feature | The ultimate Android tablet experience'
WHERE name = 'Samsung Galaxy Tab S9';

-- ─── Speaker ─────────────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Incredible sound for such a compact size | Portable and fits in any bag or pocket | Battery lasts about 10 hours | IP67 water and dust resistant, took it to the beach | JBL bass is punchy and satisfying | Pairs easily with phone via Bluetooth | Durable build survives accidental drops | Good for outdoor use and travel | USB-C charging is convenient | Best mini portable speaker available'
WHERE name = 'Trein Boom Mini';

UPDATE products SET customer_feedback = 'Loud and bassy for outdoor parties | Battery backup is impressive at 14 hours | IPX5 water resistance handles splashes | Bluetooth range is strong at 10 meters | TWS pairing with another Stone speaker works | RGB lights add to the party vibe | Microphone for hands-free calls works decently | Good build quality for the price | Volume goes loud enough for a small gathering | boAt delivers great value as always'
WHERE name = 'boAt Stone 1200';

UPDATE products SET customer_feedback = 'Clear and balanced sound for the size | Ultra-portable, weighs almost nothing | Battery lasts about 16 hours | IP67 protection for rain and dust | Multipoint connects two devices simultaneously | Clean design in multiple color options | Strap attachment is handy for hanging | Sound quality perfect for personal listening | USB-C charging is quick | Great travel companion speaker'
WHERE name = 'Sony SRS-XB100';

UPDATE products SET customer_feedback = 'Alexa smart assistant makes it genuinely useful | Sound quality improved significantly over 4th gen | Compact design fits anywhere in the home | Smart home control hub works perfectly | Music streaming quality is good for the size | Can be paired with another Echo for stereo | Intercom feature between rooms is practical | Routines automation is a daily time saver | Privacy controls are accessible | Best smart speaker for the price'
WHERE name = 'Amazon Echo Dot 5th Gen';

UPDATE products SET customer_feedback = 'Powerful sound that fills a large room | Battery lasts up to 20 hours | IP67 waterproof tested at the pool | PartyBoost links multiple JBL speakers | USB-C and USB-A for charging devices on the go | Bass radiators deliver deep low end | Built-in powerbank feature is a nice bonus | Durable build handles rough use | Bluetooth 5.1 connection is rock solid | The go-to speaker for outdoor adventures'
WHERE name = 'JBL Charge 5';

UPDATE products SET customer_feedback = 'Google Assistant is great for smart home control | Compact size fits on any shelf or table | Sound is decent for such a small speaker | Pairs well with other Nest speakers | Voice match recognizes different family members | Quick responses to voice commands | Good for kitchen timers and basic music | Affordable smart home starting point | Privacy mute switch is reassuring | Perfect for someone entering the smart speaker world'
WHERE name = 'Google Nest Mini';

UPDATE products SET customer_feedback = 'Sound quality is audiophile-grade for a portable speaker | Iconic Marshall design looks fantastic anywhere | Battery lasts about 30 hours | IPX7 water resistance adds peace of mind | Multi-directional sound fills the room evenly | Bluetooth 5.1 connection is stable | Built-in equalizer knobs are a nice analog touch | Stack Mode with other Marshall speakers is cool | Compact yet powerful for its size | Premium speaker for those who value sound quality'
WHERE name = 'Marshall Emberton II';

UPDATE products SET customer_feedback = 'Best budget speaker under 500 rupees | Sound is surprisingly decent for the price | Compact and ultra-portable | Battery lasts about 4-5 hours | Micro USB charging is the only downside | FM radio is a bonus feature | Micro SD card slot for offline music | Call function works in a pinch | Build feels sturdy enough for daily use | Perfect for a personal desk or bedside speaker'
WHERE name = 'Zebronics Zeb-County';

-- ─── Mixer Grinder ───────────────────────────────────────────────────
UPDATE products SET customer_feedback = 'Powerful 750W motor handles all grinding tasks | 3 jars cover everything from chutneys to dry grinding | Blades are sharp and durable stainless steel | Grinds idli batter smoothly | Easy to operate with clear speed controls | Motor does not heat up during extended use | Compact base does not take much counter space | Jars are easy to clean | Trusted Bajaj quality and after-sales | Best mixer grinder for Indian kitchen needs'
WHERE name = 'Trein PowerMix 750';

UPDATE products SET customer_feedback = 'Most versatile mixer grinder I have owned | Master Chef jar for kneading and chopping is unique | Powerful motor handles everything from dry masala to juicing | Multiple jars and attachments cover every kitchen task | Centrifugal juicing attachment works well | Easy to clean with detachable parts | Build quality is premium South Indian engineering | Motor is robust and does not stall | Preethi service is prompt and reliable | Worth the investment for daily Indian cooking'
WHERE name = 'Preethi Zodiac';

UPDATE products SET customer_feedback = 'Compact and powerful for daily grinding needs | 3 jars are the right sizes for an Indian kitchen | Motor handles dry and wet grinding smoothly | Sturdy build quality from Philips | Easy to assemble and disassemble jars | Low noise compared to other grinders | Blade design grinds evenly | Easy to clean jars and blades | Reliable brand with good service network | Good value mixer grinder for everyday use'
WHERE name = 'Philips HL7756';

UPDATE products SET customer_feedback = 'Affordable and gets the job done for daily use | 4 jars at this price is excellent value | Suitable for all basic grinding and mixing needs | Motor power is adequate for home cooking | Simple controls make it easy for anyone | Compact design fits small kitchen counters | Butterfly brand is trusted in South India | Jars are easy to lock and unlock | Handles wet grinding well for batters | Good entry-level mixer grinder'
WHERE name = 'Butterfly Rapid';

UPDATE products SET customer_feedback = 'German engineered motor is powerful and consistent | TrueMixx technology extracts maximum nutrition | Stone pounding blades give authentic texture to chutneys | Leak-proof jars are a thoughtful design | Handles continuous grinding without overheating | 4 jars cover all kitchen requirements | Build quality feels premium | Easy to clean with smoothly finished jars | Bosch service is professional and reliable | Premium mixer grinder worth the price'
WHERE name = 'Bosch TrueMixx Pro';

UPDATE products SET customer_feedback = 'Stylish design looks great on the kitchen counter | 3 stainless steel jars are easy to clean | Motor handles daily grinding and mixing well | Low noise operation is a plus | Comfortable grip handles on jars | Good suction feet keep it stable during operation | Overload protector keeps the motor safe | Prestige brand is trusted for kitchen appliances | Good after-sales service | Solid mid-range mixer grinder option'
WHERE name = 'Prestige Iris';

UPDATE products SET customer_feedback = 'Great value mixer grinder with powerful motor | 3 jars are adequate for daily kitchen needs | Handles dry spice grinding effortlessly | Wet grinding for batters works smoothly | Overload protection is a safety plus | Easy to operate speed controls | Build quality is decent for the price | Compact and does not occupy too much space | Havells service center helped with a query | Good option in the budget segment'
WHERE name = 'Havells Endura';

UPDATE products SET customer_feedback = 'Food processor attachment is a genuine bonus | Multiple blades and discs for chopping and slicing | Powerful motor handles tough ingredients | 4 jars plus processor cover every kitchen task | Good for making everything from puree to dry masala | Atta kneading attachment saves effort | Build quality is sturdy and reliable | Easy to clean with detachable blade system | Inalsa support was responsive | Best value food processor plus mixer grinder combo'
WHERE name = 'Inalsa Robot Chef+';
