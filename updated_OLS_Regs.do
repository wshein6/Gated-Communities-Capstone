cd "C:\Users\willi\Downloads"
import excel "GatedCommunitiesXLversion.xlsx", firstrow clear
ssc install outreg2
ssc install rdrobust, replace
ssc install rdplot, replace
ssc install rddensity, replace

*variables
gen has_security =  (gate_restricted_entrance == 1 | general_security == 1| guards == 1 | wall == 1)

gen has_rec = (parks ==1 | public_amenities ==1 | commercial_areas ==1 | community_centers_clubs == 1)

gen has_util = (electricity_backup ==1 | electricity_grid_stations ==1 | gas_general == 1 | sewage_drainage_system ==1 | util_general ==1 | water_general ==1 | water_filtration_plants ==1 | water_overhead_tanks ==1 | water_underground_tanks ==1 )

gen has_water = (water_general ==1 | water_filtration_plants ==1 | water_overhead_tanks ==1 | water_underground_tanks ==1)

gen has_electricity= (electricity_backup ==1 | electricity_grid_stations ==1)

gen resid_util = (gas_general == 1 | sewage_drainage_system ==1 | util_general ==1)

gen has_QOL = (healthcare ==1 | roads_transport == 1 |governance ==1 | education == 1)




gen in_lahore = (city == "lahore")

gen in_faisalabad = (city == "faisalabad")

gen in_bahawalpur = (city == "bahawalpur")

gen in_gujranwala = (city == "gujranwala")

gen in_gwadar = (city == "gwadar")

gen in_hyderabad = (city == "hyderabad")

gen in_islamabad = (city == "islamabad")

gen in_karachi = (city == "karachi")

gen in_multan = (city == "multan")

gen in_peshawar = (city == "peshawar" )

gen in_rawalpindi = (city == "rawalpindi")

gen in_sahiwal = (city == "sahiwal")

gen in_sargodha = (city == "sargodha")

gen in_sialkot = (city == "sialkot")

gen DHA = (society_map_parent_society_clean == "DHA Defence")

encode city, gen(city_id)

*FE Construction

egen city_fe = group(city)

* ── Step 2: Set base category ──
fvset base 1 city_fe

* ── Step 3: FE construction ──
tab city, gen(CITY)



in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot 






putexcel set "OLS_Regs.xlsx", sheet("Results") replace
**Reg 1: All
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general  general_security guards healthcare parks patrol public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general wall water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0


**Reg 2: Selected
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0
estimates store m1




lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general wall water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0, selection(cv)
lassocoef


reg gate_restricted_entrance parks religious_sites roads_transport sewage_drainage_system water_overhead_tanks water_filtration_plants education if society_map_subsociety == 0
estimates store m2


reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education 
estimates store m3

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0
estimates store m4

*security 
reg gate_restricted_entrance general_security guards wall if society_map_subsociety == 0
estimates store m5

reg has_security electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0 
estimates store m6


*FE regs 
**setting up city FE
xtset city_id
xtreg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0, fe
estimates store m7

xtset city_id
xtreg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education society_map_subsociety, fe
estimates store m8

xtset city_id
xtreg gate_restricted_entrance general_security guards wall  if  society_map_subsociety == 0, fe
estimates store m9






etable, estimates(m1 m2 m3 m4 m5 m6 m7 m8 m9) mstat(N) mstat(r2) export(present_results.xlsx, replace)

*dummies 


reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot  if  society_map_subsociety == 0 
estimates store m1

lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot  if  society_map_subsociety == 0
lassocoef

*lasso
reg gate_restricted_entrance parks religious_sites roads_transport sewage_drainage_system water_overhead_tanks water_filtration_plants education in_islamabad in_karachi if society_map_subsociety == 0
estimates store m2

*subsociety status as regressor 
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety 
estimates store m3

lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety 
lassocoef 

reg gate_restricted_entrance electricity_backup parks religious_sites sewage_drainage_system water_overhead_tanks water_filtration_plants education if society_map_subsociety == 0 | society_map_subsociety == 1
estimates store m7

*for curiosity's sake, included state dummies 
reg gate_restricted_entrance electricity_backup parks religious_sites sewage_drainage_system water_overhead_tanks water_filtration_plants education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot if society_map_subsociety == 0 | society_map_subsociety == 1 
estimates store m4


*security regs 

reg gate_restricted_entrance general_security guards wall in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot if society_map_subsociety == 0 | society_map_subsociety == 1 
estimates store m5

reg gate_restricted_entrance general_security guards wall in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety
estimates store m6

reg has_security electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot if  society_map_subsociety == 0 | society_map_subsociety == 1
estimates store m8

reg has_security electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety
estimates store m9






etable, estimates(m1 m2 m3 m4 m5 m6 m7 m8 m9) mstat(N) mstat(r2) mstat(r2_a) export(newdummyregs.xlsx, replace)

*DHA Dummy 

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA
estimates store m1


reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot DHA if society_map_subsociety == 0
estimates store m2

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_gujranwala in_gwadar in_hyderabad in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot DHA if society_map_subsociety == 0 |  society_map_subsociety == 1
estimates store m3



reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur  in_islamabad DHA if society_map_subsociety == 0
estimates store m4

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA

etable, estimates(m1 m2 m3 m4) mstat(N) mstat(r2) mstat(r2_a) export(DHAdummyregs.xlsx, replace)

**Regs with city dummies, dha dummies, post lasso with distance 

area_km2

*all dummies
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA area_km2
estimates store m1

*lasso city dummies



*lasso total
lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA area_km2
lassocoef

reg gate_restricted_entrance electricity_backup electricity_grid_stations parks religious_sites roads_transport sewage_drainage_system water_overhead_tanks water_filtration_plants education community_centers_clubs DHA
estimates store m2

*main com. only

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot DHA area_km2 if society_map_subsociety == 0
estimates store m3

lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot DHA area_km2 if society_map_subsociety == 0
lassocoef

reg gate_restricted_entrance parks religious_sites roads_transport sewage_drainage_system water_filtration_plants water_overhead_tanks education community_centers_clubs in_karachi if society_map_subsociety == 0
estimates store m4 

etable, estimates(m1 m2 m3 m4) mstat(N) mstat(r2) mstat(r2_a) export(distanceregs.xlsx, replace)


**for presentation 

*FE ln(distance)

gen ln_area = ln(area_km2)

reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe society_map_subsociety DHA ln_area 
estimates store m1

*FE lasso 

lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe society_map_subsociety DHA ln_area
lassocoef

reg gate_restricted_entrance electricity_backup electricity_grid_stations parks religious_sites sewage_drainage_system water_overhead_tanks water_filtration_plants education community_centers_clubs DHA ln_area if society_map_subsociety == 0 | society_map_subsociety == 1
estimates store m2

*By City Dummmies 
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA ln_area
estimates store m3

*Dummies Lasso 
lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs in_lahore in_faisalabad in_bahawalpur in_islamabad in_karachi in_multan in_peshawar in_rawalpindi in_sahiwal in_sargodha in_sialkot society_map_subsociety DHA ln_area if society_map_subsociety == 0 | society_map_subsociety == 1 
lassocoef

reg gate_restricted_entrance electricity_backup electricity_grid_stations parks religious_sites sewage_drainage_system water_overhead_tanks water_filtration_plants education community_centers_clubs DHA if society_map_subsociety == 0 | society_map_subsociety == 1
estimates store m4

*main communities only 
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe DHA ln_area if society_map_subsociety == 0
estimates store m5


*main communities lasso
lasso linear gate_restricted_entrance electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe DHA ln_area if society_map_subsociety == 0
lassocoef 

reg gate_restricted_entrance parks religious_sites sewage_drainage_system water_overhead_tanks water_filtration_plants education community_centers_clubs ln_area if society_map_subsociety == 0
estimates store m6
*has_security 
reg has_security electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe society_map_subsociety DHA ln_area
estimates store m7 
*has_security lasso
lasso linear has_security electricity_backup electricity_grid_stations gas_general healthcare parks public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education commercial_areas community_centers_clubs city_fe society_map_subsociety DHA ln_area
lassocoef
reg has_security healthcare parks sewage_drainage_system water_general education community_centers_clubs society_map_subsociety
estimates store m8
etable, estimates(m1 m2 m3 m4 m5 m6 m7 m8) mstat(N) mstat(r2) mstat(r2_a) export(intermediatepresentation.docx, replace)

*Family regs 

*security regs 
reg has_security has_rec has_util has_QOL religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m1

reg has_security has_rec has_water has_electricity has_QOL resid_util religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m2

*general family regs 
reg has_rec has_security has_water has_electricity has_QOL resid_util religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m3

reg has_water has_security has_rec has_electricity has_QOL resid_util religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m4

reg has_electricity has_water has_security has_rec has_QOL resid_util religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m5

reg has_QOL has_water has_security has_rec has_electricity resid_util religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m6

reg resid_util has_QOL has_water has_security has_rec has_electricity religious_sites city_fe society_map_subsociety DHA ln_area
estimates store m7

etable, estimates(m1 m2 m3 m4 m5 m6 m7) mstat(N) mstat(r2) mstat(r2_a) export(familyregs.docx, replace)


