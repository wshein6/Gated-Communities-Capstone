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
putexcel A2 = etable
margins, dydx(*)
putexcel A7 = etable
margins, at(healthcare=(0 1) parks=(0 1))
putexcel A12 = etable

***reg 2 gates on healthcare energybackup 

probit gate_restricted_entrance healthcare electricity_backup
putexcel A19 = etable
margins, dydx(*)
putexcel A24 = etable
margins, at(healthcare=(0 1) electricity_backup=(0 1))
putexcel A30 = etable

***reg 3 healthcare on gates energybackup

probit healthcare gate_restricted_entrance electricity_backup
putexcel A38 = etable
margins, dydx(*)
putexcel A44 = etable
margins, at(gate_restricted_entrance=(0 1) electricity_backup=(0 1))
putexcel A51 = etable

***reg 4 gates on parks religious sites
probit gate_restricted_entrance parks religious_sites 
putexcel A59 = etable
margins, dydx(*)
putexcel A65 = etable
margins, at(parks=(0 1) religious_sites=(0 1))
putexcel A70 = etable

***reg 5 gates on parks religious sites public amenities
probit gate_restricted_entrance parks religious_sites public_amenities
putexcel A77 = etable
margins, dydx(*)
putexcel A82 = etable
margins, at(parks=(0 1) religious_sites=(0 1) public_amenities=(0 1))
putexcel A87 = etable



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

