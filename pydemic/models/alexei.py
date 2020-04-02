__copyright__ = """
Copyright (C) 2020 George N Wong
Copyright (C) 2020 Zachary J Weiner
"""

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from datetime import datetime, timedelta
import numpy as np
from pydemic import Reaction, Simulation #, SplitReaction
from pydemic.models import LikelihoodEstimatorBase


class AlexeiModelSimulation(Simulation):
    """
    Each compartment has n=9 age bins (demographics)
    ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]

    Interactions between compartments are according to equations
    [TODO FIXME src/ref] in the pdf
    and are encapsulated in the reactions definition below.
    """

    def beta(self, t, y):
        phase = 2. * np.pi * (t-self.peak_day)/365
        return self.avg_infection_rate * (1. + self.seasonal_forcing * np.cos(phase))

    #def __init__(self, epidemiology, severity, imports_per_day,
    #             n_age_groups, containment):

    def __init__(self, **kwargs):
        """
        :arg serial_mu: Mean of the (gamma distribution) serial interval.

        :arg serial_std: Standard deviation of the (gamma distribution) serial interval.

        :arg R0: Conventional R0 parameter for infectivity.
      
        """

        """
          Suppose we are told we want a Gamma(mu,sig).

          Then we should make k regular reactions each with 
          rate mubar where

            k = Int(mu/sig)^2
            mubar = mu/k
        """

        # translate serial parameters into coefficient
        serial_mu = kwargs.pop('serial_mu', 5.)
        serial_std = kwargs.pop('serial_std', 3.)
        serial_k = int(serial_mu*serial_mu/serial_std/serial_std)
        serial_mubar = serial_mu / serial_k
        r0 = kwargs.pop('r0', 2.7)

        # get coefficients for basic S-E-I-R loop. these are inverse
        # rates (i.e., directly multiply them). we solve for the 
        # final coefficient by recalling R0 ~ S2E / I2R
        S2E = 1. / serial_mubar 
        E2I = S2E
        I2R = S2E / r0

        # translate incubation time into coefficients
        incubation_mu = 6.
        incubation_std = 3.
        incubation_k = int(incubation_mu*incubation_mu/incubation_std/incubation_std)
        incubation_mubar = incubation_mu / incubation_k

        # now model confirmed cases according to P_c and t_c parameters
        P_c = kwargs.pop('P_c', 0.8)  # what percentage of cases are ever confirmed
        t_c = kwargs.pop('t_c', 7.5)  # what is the timescale for confirmed cases

        # and also model hospitalized persons
        P_h = 0.2     # of people who are infected, how many go to the hospital ()
        P_d = 0.01    # of people who are infected, how many end up dying
        t_icu = 10.   # time between onset and icu admission
        t_dead = 7.5  # time between icu admission and death
        t_h = 0.05      # could not find on Alexei's blog post
        t_r = 1.      # could not find on Alexei's blog post

        reactions = (
            Reaction("susceptible", "exposed", 
                     lambda t, y: y.infectious.sum() * y.susceptible / self.total_population * S2E),
            Reaction("exposed", "infectious",
                     lambda t, y: y.exposed * E2I),
            Reaction("infectious", "removed",
                     lambda t, y: y.infectious * I2R),

            Reaction(None, "confirmation_cases_base_1",  ## should be gamma with k = 3+
                     lambda t, y: y.infectious.sum() * y.susceptible / self.total_population * S2E),
            Reaction("confirmation_cases_base_1", "confirmation_cases_base_2",
                     lambda t, y: y.confirmation_cases_base_1 / incubation_mubar),
            Reaction("confirmation_cases_base_2", "confirmation_cases_base_3",
                     lambda t, y: y.confirmation_cases_base_2 / incubation_mubar),
            Reaction("confirmation_cases_base_3", "confirmation_cases_base",
                     lambda t, y: y.confirmation_cases_base_3 / incubation_mubar),

            Reaction("confirmation_cases_base", "confirmed_yes",   # how many are ultimately confirmed
                     lambda t, y: P_c * y.confirmation_cases_base / t_c), 
            Reaction("confirmation_cases_base", "confirmed_no",    # not needed, but maybe useful for accounting?
                     lambda t, y: (1. - P_c) * y.confirmation_cases_base / t_c),

            Reaction(None, "hospitalized_cases_base_1",  ## should be gamma with k = 3+
                     lambda t, y: P_d * y.infectious.sum() * y.susceptible / self.total_population * S2E),
            Reaction("hospitalized_cases_base_1", "hospitalized_cases_base_2",
                     lambda t, y: y.hospitalized_cases_base_1 / incubation_mubar),
            Reaction("hospitalized_cases_base_2", "hospitalized_cases_base_3",
                     lambda t, y: y.hospitalized_cases_base_2 / incubation_mubar),
            Reaction("hospitalized_cases_base_3", "hospitalized_cases_base",
                     lambda t, y: y.hospitalized_cases_base_3 / incubation_mubar),
            
            Reaction("hospitalized_cases_base", "hospitalized_icu_will_die",
                     lambda t, y: y.hospitalized_cases_base / t_icu),
            Reaction("hospitalized_icu_will_die", "hospitalized_died",
                     lambda t, y: y.hospitalized_icu_will_die / t_dead),

            
            # Reaction("hospitalized_cases_base", "hospitalized_will_recover",
            #          lambda t, y: (P_h - P_d) * y.hospitalized_cases_base / t_h),
            # Reaction("hospitalized_will_recover", "hospitalized_recovered",
            #          lambda t, y: y.hospitalized_will_recover / t_r),

            # Reaction("hospitalized_cases_base", "hospitalized_never",
            #          lambda t, y: (1. - P_h) * y.hospitalized_cases_base / t_h)
        )


        super().__init__(reactions)

    def get_initial_population(self, total=1.e4):



        # FIXME: set total_population in the run method(s)
        self.total_population = total


        """
        # FIXME: remove this method?
        N = population.population_served
        n_age_groups = len(age_distribution.counts)
        age_counts = age_distribution.counts
        """
        y0 = { }
        for compartment in self.compartments:
            y0[compartment] = np.array([0.])
        """
        y0 = {
            'susceptible': np.round(np.array(age_counts) * N / np.sum(age_counts)),
            'exposed': np.zeros(n_age_groups),
            'infectious': np.zeros(n_age_groups),
            'recovered': np.zeros(n_age_groups),
            'hospitalized': np.zeros(n_age_groups),
            'critical': np.zeros(n_age_groups),
            'dead': np.zeros(n_age_groups)
        }
        """
        y0['susceptible'] = self.total_population
        y0['exposed'] = 10.

        return y0

    def get_days_float(self, time_tuple):
        t_diff = datetime(*time_tuple) - datetime(2020, 1, 1)
        return t_diff.total_seconds() / timedelta(days=1).total_seconds()

    def __call__(self, t_span, y0, dt=.01, **kwargs):
        t_start = self.get_days_float(t_span[0])
        t_end = self.get_days_float(t_span[1])
        return super().__call__([t_start, t_end], y0, dt=dt, **kwargs)

    def solve_deterministic(self, t_span, y0, **kwargs):
        t_start = self.get_days_float(t_span[0])
        t_end = self.get_days_float(t_span[1])
        return super().solve_deterministic([t_start, t_end], y0, **kwargs)


class NeherModelEstimator(LikelihoodEstimatorBase):
    def get_log_likelihood(self, parameters):
        if not self.check_within_bounds(list(parameters.values())):
            return -np.inf

        model_data = self.get_model_data(
            self.data['t'], **parameters, **self.fixed_values
        )

        likelihood = -1/2 * self.norm(model_data.y['dead'].sum(axis=-1),
                                      self.data['dead'])
        return likelihood

    def get_model_data(self, t, **kwargs):
        start_date = datetime(2020, 1, 1) + timedelta(kwargs.pop('start_day'))
        end_date = datetime(2020, 1, 1) + timedelta(kwargs.pop('end_day'))
        start_date = (2020, start_date.month, start_date.day,
                      start_date.hour, start_date.minute, start_date.second)
        end_date = (2020, end_date.month, end_date.day,
                    end_date.hour, end_date.minute, end_date.second)

        from pydemic.load import (get_country_population_model,
                                  get_age_distribution_model)
        country = kwargs.get('country')
        subregion = kwargs.get('subregion', country)
        population = get_country_population_model(country)
        from pydemic import PopulationModel
        population = PopulationModel(
            country='United States of America',
            cases='USA-Illinois',
            population_served=12659682,
            suspected_cases_today=10,  # original 215
            ICU_beds=1e10,  # originally 1055
            hospital_beds=1e10,  # originally 31649
            imports_per_day=1.1   # originally 5.0
        )
        age_distribution = get_age_distribution_model(subregion)
        n_age_groups = len(age_distribution.counts)

        from pydemic import SeverityModel, EpidemiologyModel, ContainmentModel
        severity = SeverityModel(
            id=np.array([0, 2, 4, 6, 8, 10, 12, 14, 16]),
            age_group=np.arange(0., 90., 10),
            isolated=np.array([0., 0., 0., 0., 0., 0., 0., 0., 0.]),
            confirmed=np.array([5., 5., 10., 15., 20., 25., 30., 40., 50.]),
            severe=np.array([1., 3., 3., 3., 6., 10., 25., 35., 50.]),
            critical=np.array([5., 10., 10., 15., 20., 25., 35., 45., 55.]),
            fatal=np.array([30., 30., 30., 30., 30., 40., 40., 50., 50.]),
        )
        epidemiology = EpidemiologyModel(
            r0=kwargs.get('r0'),
            incubation_time=1,
            infectious_period=5,
            length_hospital_stay=7,
            length_ICU_stay=7,
            seasonal_forcing=0.2,
            peak_month=0,
            overflow_severity=2
        )

        mitigation_day = kwargs.pop('mitigation_day')
        cdate = datetime(2020, 1, 1) + timedelta(days=mitigation_day)
        mitigation_date = (cdate.year, cdate.month, cdate.day)
        mitigation_factor = kwargs.pop('mitigation_factor')
        mitigation_width = kwargs.pop('mitigation_width')

        containment = ContainmentModel((2019, 1, 1), (2020, 12, 1))
        containment.add_sharp_event(mitigation_date, mitigation_factor,
                                    dt_days=mitigation_width)

        from pydemic.models import NeherModelSimulation
        sim = NeherModelSimulation(
            epidemiology, severity, population.imports_per_day,
            n_age_groups, containment
        )
        y0 = sim.get_initial_population(population, age_distribution)

        result = sim.solve_deterministic((start_date, end_date), y0)
        return sim.dense_to_logger(result, t)