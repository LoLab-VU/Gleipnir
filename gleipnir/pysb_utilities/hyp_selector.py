import numpy as np
import pandas as pd
import os
import shutil
import glob
import importlib
import warnings
import multiprocessing
from multiprocessing import Pool
try:
    import HypBuilder
    from HypBuilder import ModelAssembler
except ImportError as err:
    raise err
import pysb
try:
    import cPickle as pickle
except ImportError:
    import pickle
# try:
#     import dill
# except ImportError as err:
#     raise err

from .nestedsample_it import NestedSampleIt

_hypb_dir = os.path.dirname(HypBuilder.__file__)
library_file = os.path.join(_hypb_dir, "HB_library.txt")

class HypSelector(object):
    """A model hypotheses selector based on HypBuilder and Nested Sampling-based model selection.

    Args:
        model_csv (str): Filename of the input HypBuilder model csv file.
        hb_library (str): Filename of the input HypBuilder library file.
            Defaults to None. If None then the default library from HypBuilder
            will be used; i.e., HypBuilder/HB_library.txt

    Attributes:
        nested_samplers (list of :obj:): A list containing the Nested Sampler
            objects. Must call the gen_nested_samplers function build the
            Sampler instances.
        selection (pandas.DataFrame): The DataFrame containing the sorted
            set of models, including their name, log_evidence, and
            log_evidence_error values. The values are sorted in descending
            order by the log_evidence values. Only generated after calling
            the run_nested_sampling function.
        models (list of :obj:pysb.Model): The list of models that were
            created by HypBuilder. Must call the load_models function
        model_csv
        hb_library

    """

    def __init__(self, model_csv, hb_library=None):
        """Inits HypSelector."""
        #self.model_csv = os.path.abspath(model_csv)
        self.model_csv = model_csv
        if hb_library is None:
            self.hb_library = library_file
        else:
            self.hb_library = hb_library
        self.nested_samplers = None
        self._nested_sample_its = None
        self.selection = None
        self._mod_basename = os.path.basename(self.model_csv).split('.')[0]
        self._hypb_outputdir = os.path.join('./output',self._mod_basename)

        # Assemble the models
        ModelAssembler(self.hb_library, self.model_csv)
        # get the output models
        self._model_files = glob.glob(os.path.join(self._hypb_outputdir,'model_*.py'))
        print(self._model_files)
        # Now lets make a new models dir with an __init__.py, so we can easily
        # import all the models
        try:
            os.makedirs('hb_models')
        except OSError:
            pass
        with open('hb_models/__init__.py','w') as init:
            pass

        for model_file in self._model_files:
            mbase = os.path.basename(model_file)
            new_path = os.path.join('./hb_models', mbase)
            os.rename(model_file, new_path)
        self._model_files = glob.glob(os.path.join('hb_models','model_*.py'))
        print(self._model_files)
        # Remove the old outputs dir
        try:
            shutil.rmtree('./output')
        except OSError:
            pass
        # Load the models
        self.models = None
        # self.load_models()
        # for i, model_file in enumerate(self._model_files):
        #         model_module = importlib.import_module("hb_models.model_{}".format(i))
        #         model = getattr(model_module, 'model')
        #         self.models.append(model)
        return

    def load_models(self):
        """Loads instances of the models (pysb.Model) created by HypBuilder.

        Returns
            None
        """
        # Load the models
        self.models = list()
        for i, model_file in enumerate(self._model_files):
                model_module = importlib.import_module("hb_models.model_{}".format(i))
                model = getattr(model_module, 'model')
                self.models.append(model)
        return

    def number_of_models(self):
        """Number of models that were generated by HypBuilder.

        Returns:
            int: The number of models.

        """
        return len(self._model_files)

    def append_to_models(self, line):
        """Append a line to each of model files.
        This function can be used add a new line to each of the model files
        that was generated by HypBuilder. E.g., to add a new observable
        to each model.

        Args:
            line (str): The line of text to append to the model files.

        Returns
            None
        """
        for mf in self._model_files:
            with open(mf,'a') as mfo:
                mfo.write(line)
        return

    def gen_nested_samplers(self, timespan, observable_data,
                        solver=pysb.simulator.ScipyOdeSimulator,
                        solver_kwargs=dict(), ns_version='gleipnir-classic',
                        ns_population_size=1000, ns_kwargs=dict(),
                        log_likelihood_type='logpdf'):
        """Generate the Nested Sampling objects for each model.

        The Nested Sampling object instances are stored in a list as the
        `nested_samplers` attribute.

        Args:
            timespan (numpy.array): The timespan for model simulations.
            observable_data (dict of tuple): Defines the observable data to
                use when computing the loglikelihood function. It is a dictionary
                keyed to the model Observables (or species names) that the
                data corresponds to. Each element is a 3 item tuple of format:
                (:numpy.array:data, None or :numpy.array:data_standard_deviations,
                None or :list like:time_idxs or :list like:time_mask).
            solver (:obj:): The ODE solver to use when running model simulations.
                Defaults to pysb.simulator.ScipyOdeSimulator.
            solver_kwargs (dict): Dictionary of optional keyword arguments to
                pass to the solver when it is initialized. Defaults to dict().
            ns_version (str): Defines which version of Nested Sampling to use.
                Options are 'gleipnir-classic'=>Gleipnir's built-in implementation
                of the classic Nested Sampling algorithm, 'multinest'=>Use the
                MultiNest code via Gleipnir, 'polychord'=>Use the PolyChord code
                via Gleipnir, or 'dnest4'=>Use the DNest4 program via Gleipnir.
                Defaults to 'gleipnir-classic'.
            ns_population_size (int): Set the size of the active population
                of sample points to use during Nested Sampling runs.
                Defaults to 1000.
            ns_kwargs (dict): Dictionary of any additional optional keyword
                arguments to pass to NestedSampling object constructor.
                Defaults to dict().
            log_likelihood_type (str): Define the type of loglikelihood estimator
                to use. Options are 'logpdf'=>Compute the loglikelihood using
                the normal distribution estimator, 'mse'=>Compute the
                loglikelihood using the negative mean squared error estimator,
                'sse'=>Compute the loglikelihood using the negative sum of
                 squared errors estimator. Defaults to 'logpdf'.

        Returns:
            None
        """
        print(ns_version)
        if self.models is None:
            self.load_models()
        if ns_version == 'multinest':
            if 'sampling_efficiency' not in list(ns_kwargs.keys()):
                ns_kwargs['sampling_efficiency'] = 0.3
        ns_sample_its = list()
        ns_samplers = list()
        for i,model in enumerate(self.models):
            sample_it = NestedSampleIt(model, observable_data, timespan,
                                       solver=solver,
                                       solver_kwargs=solver_kwargs)
            ns_sampler = sample_it(ns_version,
                                   ns_population_size=ns_population_size,
                                   ns_kwargs=ns_kwargs,
                                   log_likelihood_type=log_likelihood_type)
            # Guard patch for multinest and polychord file outputs, so
            # each model run has its own file names.
            if ns_version == 'multinest':
                ns_sampler._file_root="multinest_run_model_{}_".format(i)
                # print(ns_sampler._file_root)
            elif ns_version == 'polychord':
                ns_sampler._settings.file_root="polychord_run_model_{}_".format(i)
            #elif ns_sampler:
            # if ns_version == 'multinest':
            #     print(ns_sampler._file_root)
            # quit()
            ns_sample_its.append(sample_it)
            ns_samplers.append(ns_sampler)
        self._nested_sample_its = ns_sample_its
        self.nested_samplers = ns_samplers
        return

    def run_nested_sampling(self):
        """Run Nested Sampling on each model.

        Returns:
            pandas.DataFrame: The sorted models with their log_evidence and
                log_evidence_error estimates. The DataFrame is sorted in descending
                order by the log_evidence.

        """
        nprocs = 1
        if self.nested_samplers is None:
            warnings.warn("Unable to run. Must call the 'gen_nested_samplers' function first!")
            return
        ns_samplers = self.nested_samplers
        # if nprocs > 1:
        #
        #     p = Pool(nprocs)
        #     ns_runs = p.map(_run_ns, ns_samplers)
        #     p.close()
        #     self.nested_samplers = ns_runs
        # else:
        for i in range(len(self.nested_samplers)):
            self.nested_samplers[i].run()
        frame = list()
        for i,ns in enumerate(self.nested_samplers):
            data_d = dict()
            data_d['model'] = "model_{}".format(i)
            data_d['log_evidence'] = ns.log_evidence
            data_d['log_evidence_error'] = ns.log_evidence_error
            frame.append(data_d)
        selection = pd.DataFrame(frame)
        selection.sort_values(by=['log_evidence'], ascending=False, inplace=True)
        self.selection = selection
        return selection.reset_index(drop=True)

    def bayes_factors(self):
        """Compute the Bayes factors of models using evidence ratios.

        Returns:
            pandas.DataFrame: Returns a symmetric DataFrame with the Bayes
                factors of each model combination.

        """
        n_models = self.number_of_models()
        mod_list = []
        for i in range(n_models):
            mod_list.append("model_{}".format(i))
        bayes_factors = np.ones((n_models,n_models))
        for i,nsi in enumerate(self.nested_samplers):
            loge_i = nsi.log_evidence
            for j,nsj in enumerate(self.nested_samplers):
                loge_j = nsj.log_evidence
                if i != j:
                    bf = np.exp(loge_i - loge_j)
                    bayes_factors[j,i] = bf
        return pd.DataFrame(bayes_factors, index=mod_list,
                                columns=mod_list)

    def akaike_ic(self):
        frame = list()
        for i,ns in enumerate(self.nested_samplers):
            data_d = dict()
            data_d['model'] = "model_{}".format(i)
            data_d['AIC'] = ns.akaike_ic()
            frame.append(data_d)
        aic_frame = pd.DataFrame(frame)
        aic_frame.sort_values(by=['AIC'], ascending=True, inplace=True)
        return aic_frame.reset_index(drop=True)

    def _n_data(self):
        n_dat = 0
        obs_dat = self._nested_sample_its[0].observable_data
        for item in obs_dat:
            n_dat += len(obs_dat[item][0])
        return n_dat

    def bayesian_ic(self):
        n_data = self._n_data()
        frame = list()
        for i,ns in enumerate(self.nested_samplers):
            data_d = dict()
            data_d['model'] = "model_{}".format(i)
            data_d['BIC'] = ns.bayesian_ic(n_data)
            frame.append(data_d)
        aic_frame = pd.DataFrame(frame)
        aic_frame.sort_values(by=['BIC'], ascending=True, inplace=True)
        return aic_frame.reset_index(drop=True)

def _run_ns(nested_sampler):
    nested_sampler.run()
    return nested_sampler
