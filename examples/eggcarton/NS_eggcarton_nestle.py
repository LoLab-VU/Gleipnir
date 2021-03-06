"""
Implementation of the 2-dimensional 'Egg Carton' problem and its sampling
using Nestle via Gleipnir.

Adapted from the pymultinest_demo.py at:
https://github.com/JohannesBuchner/PyMultiNest/blob/master/pymultinest_demo.py

The likelihood landscape has an egg carton-like shape; see slide 15 from:
http://www.nbi.dk/~koskinen/Teaching/AdvancedMethodsInAppliedStatistics2016/Lecture14_MultiNest.pdf

"""
import numpy as np
from scipy.stats import uniform
from gleipnir.sampled_parameter import SampledParameter
from gleipnir.nestle import NestleNestedSampling



# Number of paramters to sample is 1
ndim = 2
# Set up the list of sampled parameters: the prior is Uniform(0:10*pi) --
# we are using a fixed uniform prior from scipy.stats
sampled_parameters = [SampledParameter(name=i, prior=uniform(loc=0.0,scale=10.0*np.pi)) for i in range(ndim)]

# Define the loglikelihood function
def loglikelihood(sampled_parameter_vector):
    chi = (np.cos(sampled_parameter_vector)).prod()
    return (2. + chi)**5

if __name__ == '__main__':

    # Set up the list of sampled parameters: the prior is Uniform(0:10*pi) --
    # we are using a fixed uniform prior from scipy.stats
    sampled_parameters = [SampledParameter(name=i, prior=uniform(loc=0.0,scale=10.0*np.pi)) for i in range(ndim)]

    # Set the active point population size
    population_size = 500
    #DNest4 has additional parameters we probably want to set
    # Number of iterations -- num_steps
    num_steps = 1000
    # Number of monte carlo trial moves per iteration -- num_per_step
    num_per_step = 100
    # Number of diffusive levels
    n_levels = 10
    # Setup the Nested Sampling run
    n_params = len(sampled_parameters)
    print("Sampling a total of {} parameters".format(n_params))
    #population_size = 10
    print("Will use NS population size of {}".format(population_size))
    # Construct the Nested Sampler
    NNS = NestleNestedSampling(sampled_parameters=sampled_parameters,
                               loglikelihood=loglikelihood,
                               population_size=population_size)
    #print(PCNS.likelihood(np.array([1.0])))
    #quit()
    # run it
    log_evidence, log_evidence_error = NNS.run(verbose=True)
    # Print the output -- logZ should be approximately 236
    print("log_evidence: {} +- {} ".format(log_evidence, log_evidence_error))

    # We can also pull out an estimate of the Akaike Information Criterion (AIC)
    aic = NNS.akaike_ic()
    print("AIC estimate: {}".format(aic))
    # Bayesian Information Criterion (BIC)
    bic = NNS.bayesian_ic(2)
    print("BIC estimate: {}".format(bic))
    # Deviance Information Criterion (DIC)
    dic = NNS.deviance_ic()
    print("DIC estimate: {}".format(dic))
    #try plotting a marginal distribution
    try:
        import seaborn as sns
        import matplotlib.pyplot as plt
        # Get the posterior distributions -- the posteriors are return as dictionary
        # keyed to the names of the sampled paramters. Each element is a histogram
        # estimate of the marginal distribution, including the heights and centers.
        posteriors = NNS.posteriors()
        # Lets look at the first paramter
        marginal, edges, centers = posteriors[list(posteriors.keys())[1]]
        # Plot with seaborn
        sns.distplot(centers, bins=edges, hist_kws={'weights':marginal})
        # Uncomment next line to plot with plt.hist:
        # plt.hist(centers, bins=edges, weights=marginal)
        plt.show()
    except ImportError:
        pass
