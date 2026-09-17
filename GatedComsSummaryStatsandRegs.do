//Convert from .csv to .xlsx then import 
import excel "GatedCommunitiesXLversion.xlsx", firstrow clear


//Basic Summary Stats

estpost sum electricity_backup electricity_grid_stations gas_general gate_restricted_entrance general_security guards healthcare parks patrol public_amenities religious_sites roads_transport sewage_drainage_system street_lights_snippet telecom util_general wall water_general water_overhead_tanks water_underground_tanks

esttab using "summary_stats.csv", cells("count mean sd min max") noobs nonum nomtitle replace

//Regressions

**Probit Regs 

***Test with gates on security and guards 
probit gate_restricted_entrance general_security guards

margins, dydx(*)

margins, at(general_security=(0 1) guards=(0 1))

***** Visualization
marginsplot, xdimension(general_security) by(guards)

//Question: Are Public Services are being gatekept?
//Question: Is Healthcare being (*literally*) Gatekept
***reg 1 gates on healthcare parks  
putexcel set "probit_results.xlsx", sheet("Results") replace
probit gate_restricted_entrance healthcare parks
putexcel A1 = etable
margins, dydx(*)
putexcel A5 = etable
margins, at(healthcare=(0 1) parks=(0 1))
putexcel A9 = etable

***reg 2 gates on healthcare energybackup 

probit gate_restricted_entrance healthcare electricity_backup
putexcel A17 = etable
margins, dydx(*)
putexcel A22 = etable
margins, at(healthcare=(0 1) electricity_backup=(0 1))
putexcel A28 = etable

***reg 3 healthcare on gates energybackup

probit healthcare gate_restricted_entrance electricity_backup
putexcel A36 = etable
margins, dydx(*)
putexcel A41 = etable
margins, at(gate_restricted_entrance=(0 1) electricity_backup=(0 1))
putexcel A46 = etable

***reg 4 gates on parks religious sites
probit gate_restricted_entrance parks religious_sites 
putexcel A51 = etable
margins, dydx(*)
putexcel A55 = etable
margins, at(parks=(0 1) religious_sites=(0 1))
putexcel A60 = etable

***reg 5 gates on parks religious sites public amenities
probit gate_restricted_entrance parks religious_sites public_amenities
putexcel A68 = etable
margins, dydx(*)
putexcel A63 = etable
margins, at(parks=(0 1) religious_sites=(0 1) public_amenities=(0 1))
putexcel A71 = etable



**Logit Regs 
logit gate_restricted_entrance general_security guards





*************Visualizations 
* Visualization
marginsplot, xdimension(healthcare) by(electricity_backup)

***** Visualization
marginsplot, xdimension(healthcare) by(parks)

* Visualization
marginsplot, xdimension(healthcare) by(electricity_backup)

* Visualization
marginsplot, xdimension(gate_restricted_entrance) by(electricity_backup)

