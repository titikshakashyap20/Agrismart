"""
AgriSmart Review 2 - Soil-Water Model

A single-layer ("bucket") soil-water balance - a deliberately lightweight
stand-in for a full crop-growth simulator (DSSAT). It captures the one
thing that actually matters for irrigation TIMING to matter: soil water is
bounded (field capacity, wilting point), and anything above field capacity
is lost as drainage rather than banked for later. That nonlinearity is what
makes "dump it all at once" different from "spread it out," even for the
same total amount.

Balance equation (mm), per timestep:
    balance = soil_water[t] + rain[t] + irrigation[t] - ET[t]
    soil_water[t+1] = clip(balance, 0, field_capacity)
    drainage[t] = max(0, balance - field_capacity)

No dependency on the DE engine or yield function - pure state simulation,
testable in isolation.
"""

import numpy as np
import config


def step(soil_moisture, rain, irrigation, et,
         field_capacity=config.FIELD_CAPACITY):
    """Advance soil moisture by one timestep. Returns (new_moisture, drainage)."""
    balance = soil_moisture + rain + irrigation - et
    new_moisture = float(np.clip(balance, 0.0, field_capacity))
    drainage = max(0.0, balance - field_capacity)
    return new_moisture, drainage


def water_availability(soil_moisture,
                        field_capacity=config.FIELD_CAPACITY,
                        wilting_point=config.WILTING_POINT):
    """
    Normalized 0-1 water availability the crop actually experiences.
    0 = at/below wilting point (crop stressed), 1 = at field capacity.
    """
    assert field_capacity > wilting_point, "FIELD_CAPACITY must exceed WILTING_POINT"
    return float(np.clip(
        (soil_moisture - wilting_point) / (field_capacity - wilting_point), 0.0, 1.0
    ))


def simulate_season(initial_moisture, rain_series, et_series, irrigation_series,
                     field_capacity=config.FIELD_CAPACITY,
                     wilting_point=config.WILTING_POINT):
    """
    Runs the bucket model across a sequence of timesteps. rain_series,
    et_series and irrigation_series must be the same length (a "timestep"
    can be a day, or a coarser decision interval - the model doesn't care,
    as long as all three series use the same resolution).

    Returns dict of arrays: soil_moisture (length n+1), water_availability
    (length n), drainage (length n).
    """
    n = len(rain_series)
    assert len(et_series) == n and len(irrigation_series) == n, \
        "rain, ET and irrigation series must be the same length"

    moisture = [initial_moisture]
    availability = []
    drainage = []

    for t in range(n):
        new_m, drain = step(moisture[-1], rain_series[t], irrigation_series[t],
                             et_series[t], field_capacity)
        moisture.append(new_m)
        availability.append(water_availability(new_m, field_capacity, wilting_point))
        drainage.append(drain)

    return {
        "soil_moisture": np.array(moisture),
        "water_availability": np.array(availability),
        "drainage": np.array(drainage),
    }


if __name__ == "__main__":
    # Sanity check: no irrigation, sparse rain -> moisture should drift
    # toward the wilting point between rain events.
    n = 20
    rng = np.random.default_rng(0)
    rain = rng.exponential(3, n) * (rng.random(n) < 0.3)
    et = np.full(n, 5.0)
    irrigation = np.zeros(n)

    result = simulate_season(config.INITIAL_SOIL_MOISTURE, rain, et, irrigation)
    print("Final soil moisture (no irrigation):", result["soil_moisture"][-1])
    print("Mean water availability (no irrigation):", result["water_availability"].mean())