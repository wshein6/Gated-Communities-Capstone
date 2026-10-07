cd "C:\Users\willi\Downloads"
import excel "GatedCommunitiesXLversion.xlsx", firstrow clear
ssc install outreg2


*variables
gen has_security =  (gate_restricted_entrance == 1 | general_security == 1| guards == 1 | wall == 1)

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

encode city, gen(city_id)


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






