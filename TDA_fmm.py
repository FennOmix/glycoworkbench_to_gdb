import numpy as np
from scipy.stats import gamma as dgamma
from scipy.stats import kstest

## Calculate gaussian density function values for np.array X.
#
# @param X The input np.array.
# @param u The mean of the score X, i.e. the mu
# @param sigma The std of the score X, i.e. the sigma
def gauss_pdf(X, u, sigma):
    return 1/(np.sqrt(2*np.pi)*sigma)*np.exp(-0.5*np.square((X-u)/sigma))

## Calculate gaussian density function values for np.array X.
#
# @param X The input np.array.
# @param u The mean of the score X, i.e. the mu
# @param sigma The std of the score X, i.e. the sigma
def gamma_pdf(X, u, sigma):
    a = (u / sigma)**2
    scale = sigma**2 / u
    return dgamma.pdf(X, a = a, scale = scale)

dnorm_pdf  = gauss_pdf
dfalse_pdf = gamma_pdf
# dfalse_pdf = gauss_pdf

BIC_Max = 1e+100
Div_Zero = 1e-50
Max_Iter = 100

## Implementation of the FMM algorithm.
#
# This model could be both used to estimate both target and decoy score distributions.
class TDA_fmm(object):
    ## The constructor.
    # 
    # @param n_components The number of components of the gaussian mixtures.
    # @param max_iter Max number of iterations.
    # @param external_model External TDA_FMM model appended to the components
    # If estimating the decoy model, external_model should be set as None.
    # If estimating the target model, external_model should be a decoy model which has been fit()ed.
    def __init__(self, n_components, external_model = None):
        self.n_components = n_components
        self.external_model = external_model
        self.max_iter = Max_Iter
        if external_model is None: self.single_pdf = dfalse_pdf
        else: self.single_pdf = dnorm_pdf
        
    def __call__(self, X):
        return self.pdf_mix(X)
    
    ## Estimate posterior error probilities.
    def pep(self, X, external_pdf = None):
        if self.weights is None: return np.zeros(len(X))
        if self.external_model is not None:
            if external_pdf is None:
                external_pdf = self.external_model.pdf(X)
            return self.weights[-1]*external_pdf / self.pdf_mix(X, external_pdf)
        else:
            return np.zeros(X.shape[0])
            
    def get_pi0(self):
        if self.weights is None or self.external_model is None: return 0
        else: return self.weights[-1]
    
    ## Estimate the f1 probability density function (pdf) values for given X.
    def pdf(self, X):
        if self.weights is None: 
            return np.zeros(len(X))
        X = np.array(X)
        pdf = np.zeros((self.n_components, X.shape[0]))
        for i in range(0, self.n_components): 
            pdf[i,:] = self.single_pdf(X, u=self.mu[i], sigma=self.sigma[i])
        return np.dot(self.weights[:self.n_components], pdf)
    
    ## Estimate mixed probability density function (pdf) values for given X.
    def pdf_mix(self, X, external_pdf = None):
        if self.weights is None: return np.zeros(len(X))
        X = np.array(X)
        if self.external_model is not None:
            if external_pdf is None:
                external_pdf = self.external_model.pdf(X)
            pdf0 = external_pdf*self.get_pi0()
            pdf1 = self.pdf(X)*(1-self.get_pi0())
            return pdf0 + pdf1
        else:
            return self.pdf(X)
    
    ## Calculate the log-likelihood and BIC value given X.
    def loglik_BIC(self, X):
        if self.weights is None: return 0, 0
        if self.external_model is not None: _has_external = 1
        else: _has_external = 0
        loglik = np.sum(np.log(self.pdf(X)))
        BIC = -2*loglik + (3*self.n_components+_has_external)*np.log(len(X))
        return loglik, BIC
        
    ## Plot the mixture models
    def plot(self, title, plot_scores, false_scores = None):
        import matplotlib.pyplot as plt
        binsize = 20
        nkstest = 500
        lw = 4
        
        if self.external_model is not None and false_scores is not None:
            self.external_model.plot(title, false_scores)
            scores = np.array(plot_scores)
            binsize *= 2
            nkstest = nkstest*10
            if len(scores) < nkstest: nkstest = len(scores)
            scores = scores[np.random.permutation(len(scores))[:nkstest]]
            print("#target=%d, "%len(plot_scores) + "KS-test: KS-value=%g, p-value=%g" %kstest(scores, self))
            
            step = 0.02
            fig = plt.figure()
            pp = plt.subplot()
            
            n, bins, patches = pp.hist(scores, binsize, normed=1, facecolor='green', alpha=0.75)
            bins = np.arange(scores.min(), scores.max(), step)
            dis = self.pdf_mix(bins)
            ratio = np.mean(n) / np.mean(dis)
            dis = dis * ratio
            pp.plot(bins, dis, "r--", linewidth = lw)
            pp.set_title(title + ' target')
            
            #plot false and true distribution seperately
            fig = plt.figure()
            pp = plt.subplot()
            dis_false = self.external_model.pdf(bins)
            dis_true = self.pdf(bins)
            pp.hist(scores, binsize, normed=1, facecolor='green', alpha=0.75)
            dis_false = dis_false * ratio * self.get_pi0()
            dis_true = dis_true * ratio * (1-self.get_pi0())
            pp.plot(bins, dis_true, "b--", linewidth = lw)
            pp.plot(bins, dis_false, "r--", linewidth = lw)
            pp.set_title(title + r' target mixture ($\pi_0$=%.2f, $\pi_1$=%.2f)'%(self.get_pi0(), 1-self.get_pi0()))
            
        else:
            scores = np.array(plot_scores)
            if len(scores) < nkstest: nkstest = len(scores)
            scores = scores[np.random.permutation(len(scores))[:nkstest]]
            print("#decoy=%d, "%len(plot_scores) + "KS-test: KS-value=%g, p-value=%g" %kstest(scores, self))
            
            step = 0.1
            fig = plt.figure()
            pp = plt.subplot()
            
            n, bins, patches = pp.hist(scores, binsize, normed=1, facecolor='blue', alpha=0.75)
            bins = np.arange(scores.min(), scores.max(), step)
            dis = self.pdf(bins)
            dis = dis * np.mean(n) / np.mean(dis)
            pp.plot(bins, dis, "r--", linewidth = lw)
            pp.set_title(title + ' decoy')
            
    
    ## Fit the FMM model given data X.
    def fit(self, X):
        if len(X) < 10: 
            self.weights = None
            return
        X = np.array(X)
        self.mu = np.min(X) + (np.max(X) - np.min(X)) / (self.n_components+1) * np.array(range(1, self.n_components+1))
        self.sigma = np.ones(self.n_components) * np.var(X)
        
        if self.external_model is not None:
            d0 = self.external_model.pdf(X)
            _has_external = 1
        else:
            _has_external = 0
        
        ## weights is pi, i.e. component probabilities, including the probability of external_model.
        self.weights = np.ones(self.n_components+_has_external) / (self.n_components+_has_external)
        
        # Response of each components (including the external model), 
        # the response: $p_{ik} = w_k*f_k(X_i) / sum(w.*f)$, where k is the kth component.
        post_prob = np.zeros((self.n_components+_has_external, X.shape[0]))
          
        for __iter in range(self.max_iter):
            ## E-step
            dens = np.zeros((self.n_components+_has_external, X.shape[0]))
            
            # The external pdf is in the last
            if self.external_model is not None:
                dens[-1,:] = d0
                
            # Estimate pdf value of X for each component.
            for i in range(0, self.n_components): 
                dens[i,:] = self.single_pdf(X, u=self.mu[i], sigma=self.sigma[i])
            
            # Store the sum response, i.e. sum(w.*f), for each X_i
            total_prob = np.dot(self.weights, dens)
            # Calculate response value for each X_i
            for i in range(self.n_components+_has_external):
                post_prob[i,:] = self.weights[i] * dens[i,:] / total_prob
            
            ## M-step
            
            sum_prob = np.sum(post_prob, axis=1)
            # sum all response (R_i) for X_i to estimate the weight of each componets
            new_weights = sum_prob / np.sum(sum_prob)
            
            # New mean is the weighted mean of the responses.
            new_mu = np.dot(post_prob[:self.mu.shape[0],:], X) / sum_prob[:self.mu.shape[0]]
            new_sigma = self.sigma.copy()
            for i in range(self.n_components):
                # New std is the weighted sqrt(variance) of the response
                new_sigma[i] = np.sqrt(np.dot(post_prob[i,:], np.square((X - self.mu[i]))) / sum_prob[i])
            
            # @Todo Check if the new parameters are legal (for example NaN value).
            if np.any(np.isnan(new_sigma)) or np.any(np.isnan(new_mu)): break
            elif np.any(np.isinf(new_sigma)) or np.any(np.isinf(new_mu)): break
            elif np.any(np.array(new_sigma) <= Div_Zero) or np.any(np.array(new_mu) <= Div_Zero): break
            
            self.weights = new_weights
            self.mu = new_mu
            self.sigma = new_sigma
            
## Select best TDA_FMM (i.e. estimate the best n_components of mixture models).
#
class Select_Best_FMM:
    def __init__(self, target_scores, decoy_scores, _max_component_ = 10, verbose = False):
        self.best_fmm = None
        self.verbose = verbose
        self.fit(target_scores, decoy_scores, _max_component_)
    
    def fit(self, target_scores, decoy_scores, _max_component_ = 10):
        if self.verbose: 
            print("\n[pGlycoFDR] %d target matches, %d decoy matches"%(len(target_scores), len(decoy_scores)))
        best_decoy_fmm = None
        
        best_decoy_BIC = BIC_Max
        for n_component in range(1, _max_component_+1):
            decoy_fmm = TDA_fmm(n_component)
            decoy_fmm.fit(decoy_scores)
            log_lik, BIC = decoy_fmm.loglik_BIC(decoy_scores)
            if BIC < best_decoy_BIC:
                best_decoy_BIC = BIC
                best_decoy_fmm = decoy_fmm
            if self.verbose: print("[Decoy  FMM] G=%d, BIC=%g, best BIC=%g"%(n_component, BIC, best_decoy_BIC))
        
        best_target_BIC = BIC_Max
        for n_component in range(1, _max_component_+1):
            target_fmm = TDA_fmm(n_component, external_model=best_decoy_fmm)
            target_fmm.fit(target_scores)
            log_lik, BIC = target_fmm.loglik_BIC(target_scores)
            if BIC < best_target_BIC:
                best_target_BIC = BIC
                self.best_fmm = target_fmm
            if self.verbose: print("[Target FMM] G=%d, BIC=%f, best BIC=%f"%(n_component, BIC, best_target_BIC))
        return self

        