# References

Each method in processkit names its source. The list below gives the textbooks and papers behind each one. Page and equation numbers should be checked against your own copy before you rely on them in published or costed work.

## Heat exchangers (`unitops/heat_exchanger.py`, `docs/js/calc.js`)

- **LMTD and ε-NTU methods:** Incropera, F. P., DeWitt, D. P., Bergman, T. L. and Lavine, A. S., *Fundamentals of Heat and Mass Transfer*, Wiley. Chapter on heat exchangers.
- **LMTD correction factor for one shell pass with an even number of tube passes:** Bowman, R. A., Mueller, A. C. and Nagle, W. M. (1940), "Mean temperature difference in design", *Transactions of the ASME*, 62. The closed form in the code matches the expression in Incropera et al. and in Coulson, J. M. and Richardson, J. F., *Chemical Engineering, Volume 6: Chemical Engineering Design*, Sinnott, R. K. (ed.), Butterworth-Heinemann.

## Pipe and pump hydraulics (`unitops/hydraulics.py`)

- **Darcy-Weisbach equation and Colebrook-White friction factor:** Colebrook, C. F. (1939), "Turbulent flow in pipes, with particular reference to the transition region between the smooth and rough pipe laws", *Journal of the Institution of Civil Engineers*, 11.
- **Fitting resistance coefficients (K values):** Crane Co., *Flow of Fluids Through Valves, Fittings and Pipe*, Technical Paper No. 410 (TP-410).
- **Pump head, hydraulic power and NPSH:** Perry, R. H. and Green, D. W. (eds.), *Perry's Chemical Engineers' Handbook*, McGraw-Hill.

## Flash and vapour-liquid equilibrium (`unitops/flash.py`)

- **Rachford-Rice equation:** Rachford, H. H. and Rice, J. D. (1952), "Procedure for use of electronic digital computers in calculating flash vaporization hydrocarbon equilibrium", *Journal of Petroleum Technology*, 4(10).
- **Antoine equation constants:** NIST Chemistry WebBook, https://webbook.nist.gov/chemistry/. The benzene and toluene constants are listed there, with their temperature ranges.

## Shortcut distillation (`unitops/distillation.py`)

- **Fenske equation (minimum stages at total reflux):** Fenske, M. R. (1932), "Fractionation of straight-run Pennsylvania gasoline", *Industrial and Engineering Chemistry*, 24(5).
- **Underwood equations (minimum reflux):** Underwood, A. J. V. (1946), "Fractional distillation of multicomponent mixtures", *Journal of the Institute of Petroleum*, 32.
- **Gilliland correlation, exponential fit:** Molokanov, Yu. K. et al. (1972), as presented in Seader, Henley and Roper, *Separation Process Principles*. The code uses the form Y = 1 − exp[((1 + 54.4X)/(11 + 117.2X)) · ((X − 1)/√X)]. A simpler fit, Eduljee (1975), Y = 0.75(1 − X^0.5668), is not implemented; it gives a different result at high X and a finite stage count at minimum reflux.
- **Kirkbride equation (feed stage location):** Kirkbride, C. G. (1944), "Process design procedure for multicomponent fractionators", *Petroleum Refiner*, 23(9).
- **Overall procedure:** Seader, J. D., Henley, E. J. and Roper, D. K., *Separation Process Principles*, Wiley.

## Economics (`economics/`, `docs/js/calc.js`)

- **CEPCI cost index:** Chemical Engineering magazine, annual averages, https://www.chemengonline.com/cepci
- **Six-tenths rule for capacity scaling:** Peters, M. S., Timmerhaus, K. D. and West, R. E., *Plant Design and Economics for Chemical Engineers*, McGraw-Hill; also Turton, R. et al., *Analysis, Synthesis and Design of Chemical Processes*, Prentice Hall.
- **Capital recovery factor, NPV and IRR:** Newnan, D. G., Eschenbach, T. G. and Lavelle, J. P., *Engineering Economic Analysis*, Oxford University Press.
- **Levelised cost (LCOE and LCOH):** the constant-output form used here is the standard capital-recovery approach, described in Newnan et al. above. Simplified: it ignores tax, financing, degradation and inflation.
