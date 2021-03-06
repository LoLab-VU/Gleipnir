"""
Implementation of a 1-dimensional multi-modal likelihood problem and its
sampling using an implementation of classic Nested Sampling via Gleipnir.

Adapted from Example1 of the PyMultiNest tutorial:
http://johannesbuchner.github.io/pymultinest-tutorial/example1.html
"""

import numpy as np
from scipy.stats import uniform
from gleipnir.sampled_parameter import SampledParameter
from gleipnir.nestedsampling import NestedSampling
from gleipnir.nestedsampling.samplers import MetropolisComponentWiseHardNSRejection
from gleipnir.nestedsampling.stopping_criterion import NumberOfIterations

# Number of paramters to sample is 1
ndim = 1

# Mode positions for the multi-modal likelihood
positions = np.array([0.1, 0.2, 0.5, 0.55, 0.9, 1.1])
# its width
width = 0.01

# Define the loglikelihood function
def loglikelihood(sampled_parameter_vector):
    diff = sampled_parameter_vector[0] - positions
    diff_scale = diff / width
    l = np.exp(-0.5 * diff_scale**2) / (2.0*np.pi*width**2)**0.5
    log_like = np.log(l.mean())
    if np.isnan(log_like):
        return -np.inf
    return log_like

if __name__ == '__main__':

    # Set up the list of sampled parameters: the prior is Uniform(0:2) --
    # we are using a fixed uniform prior from scipy.stats
    sampled_parameters = [SampledParameter(name=i, prior=uniform(loc=0.0,scale=2.0)) for i in range(ndim)]
    # Setup the sampler to use when updated points during the NS run --
    # Here we are using an implementation of the Metropolis Monte Carlo algorithm
    # with component-wise trial moves and augmented acceptance criteria that adds a
    # hard rejection constraint for the NS likelihood boundary.

    sampler = MetropolisComponentWiseHardNSRejection(iterations=50, burn_in=50, tuning_cycles=2)

    # Setup the stopping criterion for the NS run -- We'll use a fixed number of
    # iterations: 10*population_size
    stopping_criterion = NumberOfIterations(1000)
    # Construct the Nested Sampler
    NS = NestedSampling(sampled_parameters=sampled_parameters,
                        loglikelihood=loglikelihood,
                        population_size=500,
                        sampler=sampler,
                        stopping_criterion=stopping_criterion)
    # run it
    log_evidence, log_evidence_error = NS.run(verbose=True)
    # Retrieve the evidence
    evidence = NS.evidence
    # Evidence should be 1/2
    print("evidence: ",evidence)
    print("log_evidence: ", log_evidence)
    best_fit_l = NS.best_fit_likelihood()
    print("Max likelihood parms: ", best_fit_l)
    best_fit_p, fit_error = NS.best_fit_posterior()
    print("Max posterior weight parms ", best_fit_p)
    print("Max posterior weight parms error ", fit_error)
    #try plotting a marginal distribution
    try:
        import seaborn as sns
        import matplotlib.pyplot as plt
        # Get the posterior distributions -- the posteriors are return as dictionary
        # keyed to the names of the sampled paramters. Each element is a histogram
        # estimate of the marginal distribution, including the heights and centers.
        posteriors = NS.posteriors()
        # Lets look at the first paramter
        marginal, edge, centers = posteriors[list(posteriors.keys())[0]]
        # Look at the moments of the first parameter
        post_moms = NS.posterior_moments()
        # Each element of the dict is a tuple with:
        # (mean, variance, skew, kurtosis)
        print(post_moms[list(post_moms.keys())[0]])
        # Plot with seaborn
        sns.distplot(centers, bins=edge, hist_kws={'weights':marginal})
        # Uncomment next line to plot with plt.hist:
        # plt.hist(centers, bins=edge, weights=marginal)
        plt.show()
    except ImportError:
        pass
