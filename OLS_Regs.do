cd "C:\Users\willi\Downloads"
import excel "GatedCommunitiesXLversion.xlsx", firstrow clear

putexcel set "OLS_Regs.xlsx", sheet("Results") replace
**Reg 1: All
reg gate_restricted_entrance electricity_backup electricity_grid_stations gas_general  general_security guards healthcare parks patrol public_amenities religious_sites roads_transport sewage_drainage_system telecom util_general wall water_general water_overhead_tanks water_underground_tanks roads_transport sewage_drainage_system util_general water_filtration_plants governance education if  society_map_subsociety == 0
putexcel A4 = etable
* Manually write model statistics below
putexcel A1 = "N"
putexcel B1 = e(N)
putexcel A2 = "R-squared"
putexcel B2 = e(r2)
putexcel A3 = "Adj. R-squared"
putexcel B3 = e(r2_a)
**Reg 2: Selected