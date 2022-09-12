"""Gateware implementation of the Sampler-Urukul (AD9910) DDS amplitude servo.

General conventions:

 - ``t_...`` signals and constants refer to time spans measured in the gateware
   module's default clock (typically a 125 MHz RTIO clock).
 - ``start`` signals cause modules to proceed with the next servo iteration iff
   they are currently idle (i.e. their value is irrelevant while the module is
   busy, so they are not necessarily one-clock-period strobes).
"""
