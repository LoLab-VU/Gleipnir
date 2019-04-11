"""Implementation on top of DNest4 via its python bindings.

This module defines the class for Nested Sampling using using the DNest4
program via its Python bindings. Note that DNest4 and its Python bindings have
to be built and installed separately (from gleipnir) before this module can be
used.

DNest4: https://github.com/eggplantbren/DNest4

References:
    1. Brewer, B., & Foreman-Mackey, D. (2018). DNest4: Diffusive Nested
        1 - 33. doi:http://dx.doi.org/10.18637/jss.v086.i07
        Sampling in C++ and Python. Journal of Statistical Software, 86(7),
    2. Brewer, B. J., Pártay, L. B., & Csányi, G. (2011). Diffusive nested
        sampling. Statistics and Computing, 21(4), 649-656

"""

import numpy as np
import pandas as pd
import warnings
try:
    import dnest4
except ImportError as err:
    #print(err)
    raise err


class _DNest4Model(object):
    """Model class for use with the Python interface to DNest4.
    Design based on the model class from the DNest4/python gaussian example:
    https://github.com/eggplantbren/DNest4/blob/master/python/examples/gaussian/gaussian.py
    """

    def __init__(self, log_likelihood_func, from_prior_func, widths, centers):
        """Initialize the DNest4 model.
        Args:
            log_likelihood_func (function): The loglikelihood function to use
                during the Nested Sampling run.
            from_prior_func (function): The function to use when randomly
                selecting parameter vectors from the prior space.
            widths (numpy.array): The approximate widths of the prior
                distrbutions.
            centers (numpy.array): The approximate center points of the prior
                distributions.
        """
        self._log_likelihood = log_likelihood_func
        self._from_prior = from_prior_func
        self._widths = widths
        self._centers = centers
        self._n_dim = len(widths)
        return

    def log_likelihood(self, coords):
        """The model's log_likelihood function"""
        return self._log_likelihood(coords)

    def from_prior(self):
        """The model's function to select random points from the prior space."""
        return self._from_prior()

    def perturb(self, coords):
        """The perturb function to perform Monte Carlo trial moves."""
        idx = np.random.randint(self._n_dim)
        coords[idx] += (self._widths[idx]*(np.random.uniform(size=1)-0.5))
        cw = self._widths[idx]
        cc = self._centers[idx]
        # Note: wrapping like this effectively truncates soft priors, which
        # may or may not be problematic; I'm not entirely sure either way.
        # However, DNest4 seems to have trouble if you don't wrap. -- Blake
        # DNest4 Note: use the return value of wrap, unlike in C++
        coords[idx] = dnest4.wrap(coords[idx], (cc-0.5*cw), cc+0.5*cw)
        return 0.0


class DNest4NestedSampling(object):
    """Nested Sampling using DNest4.
    DNest4: https://github.com/eggplantbren/DNest4

    Attributes:
        sampled_parameters (list of :obj:gleipnir.sampled_parameter.SampledParameter):
            The parameters that are being sampled during the Nested Sampling
            run.
        loglikelihood (function): The log-likelihood function to use for
            assigning a likelihood to parameter vectors during the sampling.
        population_size (int): The number of points to use in the Nested
            Sampling active population. Default: None -> gets set to
            25*(number of sampled parameters) if left at default.
        n_diffusive_levels (int, optional): The number of diffusive likelihood
            levels that DNest4 should initial during the Diffusive Nested
            Sampling run. Default: 20
        dnest4_backend (str, optional): The python DNest4 backend for storing
            the output. Options are: 'memory' and 'csv'. If 'memory' the
            DNest4 outputs are stored in memory during the run. If 'csv' the
            DNest4 outputs are written out CSV format files during the run.
            Defualt: 'memory'.
            dnest4_kwargs: Any additional DNest4 keyword arguments to be passed
                to the DNest4 sampler.
    References:
        1. Brewer, B., & Foreman-Mackey, D. (2018). DNest4: Diffusive Nested
            1 - 33. doi:http://dx.doi.org/10.18637/jss.v086.i07
            Sampling in C++ and Python. Journal of Statistical Software, 86(7),
        2. Brewer, B. J., Pártay, L. B., & Csányi, G. (2011). Diffusive nested
            sampling. Statistics and Computing, 21(4), 649-656
    """

    def __init__(self, sampled_parameters, loglikelihood, population_size=None,
                 n_diffusive_levels=20, dnest4_backend="memory",
                 **dnest4_kwargs):
        """Initialize the DNest4 Nested Sampler."""
        self.sampled_parameters = sampled_parameters
        self.loglikelihood = loglikelihood
        self.population_size = population_size
        self.dnest4_backend = dnest4_backend
        self.n_diffusive_levels = n_diffusive_levels
        self.dnest4_kwargs = dnest4_kwargs

        self._n_dims = len(sampled_parameters)
        self._log_evidence = None
        self._information = None
        self._output = None
        self._post_eval = False
        if self.population_size is None:
            self.population_size = 25*self._n_dims

        # Make the from_prior function for DNest4
        def from_prior():
            return np.array([sampled_parameter.rvs(1)[0] for sampled_parameter in self.sampled_parameters])

        self._from_prior = from_prior
        # Get the estimates of the prior distributions' widths and centers.
        widths = []
        centers = []
        for sampled_parameter in sampled_parameters:
            rv = sampled_parameter.rvs(10000)
            low = rv.min()
            high = rv.max()
            width = high - low
            center = (high+low)/2.0
            widths.append(width)
            centers.append(center)
        widths = np.array(widths)
        centers = np.array(centers)
        self._widths = widths
        self._centers = centers
        self._dnest4_model = _DNest4Model(loglikelihood, self._from_prior, widths, centers)

        return


    def run(self, verbose=False):
        """Initiate the DNest4 Nested Sampling run."""

        if self.dnest4_backend == 'csv':
            # for CSVBackend, which is output data to disk
            backend = dnest4.backends.CSVBackend(".", sep=" ")
        else:
            # for the MemoryBackend, which is output data to memory
            backend = dnest4.backends.MemoryBackend()
        sampler = dnest4.DNest4Sampler(self._dnest4_model,
                                       backend=backend)
        output = sampler.sample(self.n_diffusive_levels,
                                num_particles=self.population_size,
                                **self.dnest4_kwargs)
        self._output = output
        for i, sample in enumerate(output):
            if verbose and ((i + 1) % 100 == 0):
                stats = sampler.postprocess()
                print("Iteration: {0} log(Z): {1}".format(i+1,stats['log_Z']))
        stats = sampler.postprocess(resample=1)
        self._log_evidence = stats['log_Z']
        self._information = stats['H']
        logZ_err = np.sqrt(self._information/self.population_size)
        self._logZ_err = logZ_err
        ev_err = np.exp(logZ_err)
        self._evidence_error = ev_err
        self._evidence = np.exp(self._log_evidence)
        # To compute posterior distributions
        self._samples = np.array(sampler.backend.posterior_samples)
        # To compute AIC estimate
        # print(sampler.backend.sample_info)
        # print(len(sampler.backend.sample_info))
        # print(sampler.backend.sample_info[-1])
        # print(len(sampler.backend.sample_info[-1]))
        # print(pd.DataFrame(sampler.backend.sample_info[-1]))
        print(len(sampler.backend.samples[-1]))
        print(len(sampler.backend.weights[-1]))
        # quit()
        self._last_live_sample = sampler.backend.samples[-1]
        self._last_live_sample_weights = sampler.backend.weights[-1]
        self._last_live_sample_info = pd.DataFrame(sampler.backend.sample_info[-1])
        return self.log_evidence, self.log_evidence_error

    @property
    def evidence(self):
        """float: Estimate of the Bayesian evidence, or Z."""
        return self._evidence
    @evidence.setter
    def evidence(self, value):
        warnings.warn("evidence is not settable")

    @property
    def evidence_error(self):
        """float: Estimate (rough) of the error in the evidence, or Z.

        The error in the evidence is computed as the approximation:
            exp(sqrt(information/population_size))
        """
        return self._evidence_error
    @evidence_error.setter
    def evidence_error(self, value):
        warnings.warn("evidence_error is not settable")

    @property
    def log_evidence(self):
        """float: Estimate of the natural logarithm of the Bayesian evidence, or ln(Z).
        """
        return self._log_evidence
    @log_evidence.setter
    def log_evidence(self, value):
        warnings.warn("log_evidence is not settable")

    @property
    def log_evidence_error(self):
        """float: Estimate of the error in the natural logarithm of the evidence.
        """
        return self._logZ_err
    @log_evidence_error.setter
    def log_evidence_error(self, value):
        warnings.warn("log_evidence_error is not settable")

    @property
    def information(self):
        """float: Estimate of the Bayesian information, or H."""
        return self._information
    @information.setter
    def information(self, value):
        warnings.warn("information is not settable")

    def posteriors(self):
        """Estimates of the posterior marginal probability distributions of each parameter.
        Returns:
            dict of tuple of (numpy.ndarray, numpy.ndarray): The histogram
                estimates of the posterior marginal probability distributions.
                The returned dict is keyed by the sampled parameter names and
                each element is a tuple with (marginal_weights, bin_centers).
        """
        # Lazy evaluation at first call of the function and store results
        # so that subsequent calls don't have to recompute.
        if not self._post_eval:
            # Here the samples are samples directly from the posterior
            # (i.e. equal weights)
            samples = self._samples
            # Rice bin count selection
            nbins = 2 * int(np.cbrt(len(samples)))
            nd = samples.shape[1]
            self._posteriors = dict()
            for ii in range(nd):
                marginal, edge = np.histogram(samples[:,ii], density=True, bins=nbins)
                center = (edge[:-1] + edge[1:])/2.
                self._posteriors[self.sampled_parameters[ii].name] = (marginal, center)

            self._post_eval = True

        return self._posteriors

    def akaike_ic(self):
        """Estimate Akaike Information Criterion.
        This function estimates the Akaike Information Criterion (AIC) for the
        model simulated with Nested Sampling (NS). It does so by using the
        largest likelihood value found during the NS run and using that as
        the maximum likelihood estimate. The AIC formula is given by:
            AIC = 2k - 2ML,
        where k is number of sampled parameters and ML is maximum likelihood
        estimate.

        Returns:
            float: The AIC estimate.
        """
        mx = self._last_live_sample_info.max()
        ml = mx['log_likelihood']
        k = len(self.sampled_parameters)
        return  2.*k - 2.*ml

    def bayesian_ic(self, n_data):
        """Estimate Bayesian Information Criterion.
        This function estimates the Bayesian Information Criterion (BIC) for the
        model simulated with Nested Sampling (NS). It does so by using the
        largest likelihood value found during the NS run and taking that as
        the maximum likelihood estimate. The BIC formula is given by:
            BIC = ln(n_data)k - 2ML,
        where n_data is the number of data points used in computing the likelihood
        function fitting, k is number of sampled parameters, and ML is maximum
        likelihood estimate.

        Args:
            n_data (int): The number of data points used when comparing to data
                in the likelihood function.

        Returns:
            float: The BIC estimate.
        """
        mx = self._last_live_sample_info.max()
        ml = mx['log_likelihood']
        k = len(self.sampled_parameters)
        return  np.log(n_data)*k - 2.*ml

    def deviance_ic(self):
        """Estimate Deviance Information Criterion.
        This function estimates the Deviance Information Criterion (DIC) for the
        model simulated with Nested Sampling (NS). It does so by using the
        posterior distribution estimates computed from the NS outputs.
        The DIC formula is given by:
            DIC = p_D + D_bar,
        where p_D = D_bar - D(theta_bar), D_bar is the posterior average of
        the deviance D(theta)= -2*ln(L(theta)) with L(theta) the likelihood
        of parameter set theta, and theta_bar is posterior average parameter set.

        Returns:
            float: The DIC estimate.
        """        
        params = self._last_live_sample
        log_likelihoods = self._last_live_sample_info['log_likelihood']
        weights = self._last_live_sample_weights
        likelihoods = np.exp(log_likelihoods)
        D_of_theta = -2.*log_likelihoods
        D_bar = np.average(D_of_theta, weights=weights)
        print(D_bar)
        theta_bar = np.average(params, axis=0, weights=weights)
        print(theta_bar)
        D_of_theta_bar = -2. * self.loglikelihood(theta_bar)
        p_D = D_bar - D_of_theta_bar
        return p_D + D_bar
