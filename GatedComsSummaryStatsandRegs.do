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

****reg 1 gates on healthcare parks  

probit gate_restricted_entrance healthcare parks

margins, dydx(*)

margins, at(healthcare=(0 1) parks=(0 1))

***** Visualization
marginsplot, xdimension(healthcare) by(parks)

*****export

//Question: Is Healthcare being (*literally*) Gatekept

***reg 1 gates on healthcare energybackup 

probit gate_restricted_entrance healthcare electricity_backup

margins, dydx(*)

margins, at(healthcare=(0 1) electricity_backup=(0 1))

* Visualization
marginsplot, xdimension(healthcare) by(electricity_backup)

***Reg 2 healthcare on gates energybackup

//Question: 




**Logit Regs 
logit gate_restricted_entrance general_security guards

