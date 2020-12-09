import kagglegym
import numpy as np
import pandas as pd
import random
from sklearn import ensemble, linear_model, metrics
from sklearn.model_selection import train_test_split
import lightgbm as lgb
from sklearn.linear_model import HuberRegressor
from itertools import combinations
import gc
from threading import Thread
import multiprocessing
from multiprocessing import Manager
from sklearn import preprocessing as pp

env = kagglegym.make()
o = env.reset()
train = o.train
print(train.shape)
d_mean= train.median(axis=0)
train["nbnulls"]=train.isnull().sum(axis=1)
col=[x for x in train.columns if x not in ['id', 'timestamp', 'y']]

rnd=17

#keeping na information on some columns (best selected by the tree algorithms)
add_nas_ft=True
nas_cols=['technical_9', 'technical_0', 'technical_32', 'technical_16', 'technical_38', 
'technical_44', 'technical_20', 'technical_30', 'technical_13']

#columns kept for evolution from one month to another (best selected by the tree algorithms)
add_diff_ft=True
diff_cols=['technical_22','technical_20', 'technical_30', 'technical_13', 'technical_34']

def get_reward(y_true, y_fit):
    R2 = 1 - np.sum((y_true - y_fit)**2) / np.sum((y_true - np.mean(y_true))**2)
    R = np.sign(R2) * np.sqrt(abs(R2))
    return(R)

class createLinearFeatures:
    
    def __init__(self, n_neighbours=1, max_elts=None, verbose=True, random_state=None):
        self.rnd=random_state
        self.n=n_neighbours
        self.max_elts=max_elts
        self.verbose=verbose
        self.neighbours=[]
        self.clfs=[]
        
    def fit(self,train,y):
        if self.rnd!=None:
            random.seed(self.rnd)
        if self.max_elts==None:
            self.max_elts=len(train.columns)
        #list_vars=list(train.columns)
        #random.shuffle(list_vars)
        list_vars = ['fundamental_44', 'technical_37', 'fundamental_53', 'technical_13_na', 'fundamental_37', 'fundamental_0', 
                     'technical_14', 'fundamental_40', 'technical_44', 'technical_9', 'fundamental_23', 'technical_21', 'fundamental_25', 
                     'fundamental_55', 'fundamental_58', 'technical_33', 'fundamental_24', 'fundamental_26', 'technical_24', 
                     'fundamental_61', 'fundamental_5', 'technical_5', 'derived_1', 'technical_22_d', 'fundamental_52', 'technical_20', 
                     'fundamental_50', 'technical_9_na', 'technical_39', 'fundamental_7', 'fundamental_20', 'technical_30_d', 
                     'fundamental_59', 'fundamental_32', 'technical_43', 'technical_34_d', 'fundamental_17', 'technical_12', 
                     'fundamental_16', 'technical_30_na', 'technical_38_na', 'fundamental_12', 'technical_17', 'fundamental_63', 
                     'fundamental_30', 'fundamental_54', 'technical_20_d', 'technical_6', 'fundamental_8', 'technical_7', 'fundamental_46', 
                     'derived_4', 'technical_34', 'nbnulls', 'fundamental_19', 'fundamental_29', 'technical_10', 'fundamental_9', 
                     'technical_0_na', 'technical_30', 'technical_18', 'technical_28', 'technical_31', 'derived_0', 'technical_32_na', 
                     'fundamental_57', 'technical_25', 'fundamental_41', 'fundamental_1', 'fundamental_43', 'fundamental_51', 'derived_2', 
                     'fundamental_39', 'technical_11', 'technical_13', 'fundamental_14', 'fundamental_56', 'technical_38', 'fundamental_6', 
                     'fundamental_48', 'fundamental_35', 'fundamental_3', 'technical_36', 'fundamental_11', 'technical_16_na', 
                     'fundamental_38', 'fundamental_22', 'technical_20_na', 'technical_3', 'technical_0', 'fundamental_15', 'fundamental_21', 
                     'technical_42', 'fundamental_2', 'technical_2', 'fundamental_13', 'fundamental_47', 'technical_29', 'technical_22', 
                     'technical_16', 'fundamental_36', 'fundamental_60', 'fundamental_28', 'technical_13_d', 'technical_32', 'technical_41', 
                     'fundamental_45', 'fundamental_27', 'derived_3', 'fundamental_10', 'fundamental_31', 'technical_19', 'technical_1', 
                     'technical_44_na', 'technical_27', 'technical_35', 'fundamental_18', 'fundamental_33', 'fundamental_42', 
                     'fundamental_34', 'technical_40', 'fundamental_49', 'fundamental_62']
        
        lastscores=np.zeros(self.n)+1e15

        for elt in list_vars[:self.n]:
            self.neighbours.append([elt])
        list_vars=list_vars[self.n:]
        
        for elt in list_vars:
            indice=0
            scores=[]
            for elt2 in self.neighbours:
                if len(elt2)<self.max_elts:
                    clf=linear_model.LinearRegression(fit_intercept=False, normalize=True, copy_X=True, n_jobs=-1) 
                    clf.fit(train[elt2+[elt]], y)
                    scores.append(metrics.mean_squared_error(y,clf.predict(train[elt2 + [elt]])))
                    indice=indice+1
                else:
                    scores.append(lastscores[indice])
                    indice=indice+1
            gains=lastscores-scores
            if gains.max()>0:
                temp=gains.argmax()
                lastscores[temp]=scores[temp]
                self.neighbours[temp].append(elt)

        indice=0
        for elt in self.neighbours:
            clf=linear_model.LinearRegression(fit_intercept=False, normalize=True, copy_X=True, n_jobs=-1) 
            clf.fit(train[elt], y)
            self.clfs.append(clf)
            if self.verbose:
                print(indice, lastscores[indice], elt)
            indice=indice+1
                    
    def transform(self, train):
        indice=0
        for elt in self.neighbours:
            #this line generates a warning. Could be avoided by working and returning
            #with a copy of train.
            #kept this way for memory management
            train['neighbour'+str(indice)]=self.clfs[indice].predict(train[elt])
            indice=indice+1
        return train
    
    def fit_transform(self, train, y):
        self.fit(train, y)
        return self.transform(train)

class huber_linear_model():
    def __init__(self):

        self.bestmodel=None
        self.scaler = pp.MinMaxScaler()
       
    def fit(self, train, y):

        indextrain=train.dropna().index
        tr = self.scaler.fit_transform(train.ix[indextrain])
        self.bestmodel = HuberRegressor().fit(tr, y.ix[indextrain])
        

    def predict(self, test):
        te = self.scaler.transform(test)
        return self.bestmodel.predict(te)

class LGB_model():
    def __init__(self, num_leaves=25, feature_fraction=0.6, bagging_fraction=0.6):
        self.lgb_params = {
                'task': 'train',
                'boosting_type': 'gbdt',
                'objective': 'regression',
                'metric': {'l2'},
                'learning_rate': 0.05,
                'bagging_freq': 5,
                'num_thread':4,
                'verbose': 0
            }
        
        self.lgb_params['feature_fraction'] = feature_fraction
        self.lgb_params['bagging_fraction'] = bagging_fraction
        self.lgb_params['num_leaves'] = num_leaves
        

        self.bestmodel=None
       
    def fit(self, train, y):
        
        X_train, X_val, y_train, y_val = train_test_split(train, y, test_size=0.2, random_state=343)
        
        lgtrain = lgb.Dataset(X_train, y_train)
        lgval = lgb.Dataset(X_val, y_val, reference=lgtrain)
                
        self.bestmodel = lgb.train(self.lgb_params,
                                    lgtrain,
                                    num_boost_round=100,
                                    valid_sets=lgval,
                                    verbose_eval=False,
                                    early_stopping_rounds=5)


    def predict(self, test):
        return self.bestmodel.predict(test, num_iteration=self.bestmodel.best_iteration)

    def feature_importance(self, imptype="gain"):
        return self.bestmodel.feature_importance(importance_type=imptype)

if add_nas_ft:
    for elt in nas_cols:
        train[elt + '_na'] = pd.isnull(train[elt]).apply(lambda x: 1 if x else 0)
        #no need to keep columns with no information
        if len(train[elt + '_na'].unique())==1:
            print("removed:", elt, '_na')
            del train[elt + '_na']
            nas_cols.remove(elt)


if add_diff_ft:
    train=train.sort_values(by=['id','timestamp'])
    for elt in diff_cols:
        #a quick way to obtain deltas from one month to another but it is false on the first
        #month of each id
        train[elt+"_d"]= train[elt].rolling(2).apply(lambda x:x[1]-x[0]).fillna(0)
    #removing month 0 to reduce the impact of erroneous deltas
    train=train[train.timestamp!=0]

print(train.shape)
cols=[x for x in train.columns if x not in ['id', 'timestamp', 'y']]

tokeepmodels=[]
tokeepcolumns=[]
tokeeprewards=[]


cols2fit=['technical_22','technical_20', 'technical_30_d', 'technical_20_d', 'technical_30', 
          'technical_13', 'technical_34']

huber_models=[]
huber_columns=[]
huber_rewards=[]

#for (col1, col2) in [('technical_22', 'technical_30'), ('technical_22', 'technical_20')]:
for (col1, col2) in combinations(cols2fit, 2):    
    print("fitting Huber model on ", [col1, col2])
    model=huber_linear_model()
    model.fit(train.loc[:,[col1, col2]],train.loc[:, 'y'])
    huber_models.append(model)
    huber_columns.append([col1, col2])
    
    y_pred = pd.Series(model.predict(train[[col1, col2]].fillna(d_mean)), index=train.index, name="y_pred")
    tmp_train = pd.concat([train[['id', 'timestamp', 'y']], y_pred], axis=1)
    reward = tmp_train.timestamp.map(tmp_train.groupby('timestamp').apply(lambda x: get_reward(x['y'], x['y_pred'])))
    reward.name = "reward"
    tmp_train = pd.concat([tmp_train, reward], axis=1)
    reward_shift = tmp_train.groupby('id').apply(lambda x: x['reward'].shift(1)).fillna(0)
    
    huber_rewards.append(reward_shift)
    del y_pred, tmp_train, reward
    gc.collect()


huber_to_keep=6
targetselector=np.array(huber_rewards).T
targetselector=np.argmax(targetselector, axis=1)

print("selecting best models:")
print(pd.Series(targetselector).value_counts().head(huber_to_keep))
tokeep=pd.Series(targetselector).value_counts().head(huber_to_keep).index

for elt in tokeep:
    tokeepmodels.append(huber_models[elt])
    tokeepcolumns.append(huber_columns[elt])
    tokeeprewards.append(huber_rewards[elt])


del huber_models
del huber_columns
del huber_rewards
gc.collect()

train=train.fillna(d_mean)

print("adding new features")
featureexpander=createLinearFeatures(n_neighbours=20, max_elts=2, verbose=True, random_state=rnd)
index2use=train[abs(train.y)<0.086].index
featureexpander.fit(train.ix[index2use,cols],train.ix[index2use,'y'])
trainer=featureexpander.transform(train[cols])

treecols = trainer.columns

print("training LGB model ")

lg_models=[]
lg_columns=[]
lg_rewards=[]

num_leaves = [70]
feature_fractions = [0.2, 0.6, 0.8]
bagging_fractions = [0.7]

#with Timer("running LGB models "):
for num_leaf in num_leaves:
    for feature_fraction in feature_fractions:
        for bagging_fraction in bagging_fractions:
            print("fitting LGB tree model with ", num_leaf, feature_fraction, bagging_fraction)
            model = LGB_model(num_leaves=num_leaf, feature_fraction=feature_fraction, bagging_fraction=bagging_fraction)
            model.fit(trainer[treecols],train.y)
            print("LGB feature importance")
            print(pd.DataFrame(model.feature_importance(),index=treecols).sort_values(by=[0]).tail(20))
            print(" ")
            lg_models.append(model)
            lg_columns.append(treecols)
            
            y_pred = pd.Series(model.predict(trainer[treecols]), index=train.index, name="y_pred")
            tmp_train = pd.concat([train[['id', 'timestamp', 'y']], y_pred], axis=1)
            reward = tmp_train.timestamp.map(tmp_train.groupby('timestamp').apply(lambda x: get_reward(x['y'], x['y_pred'])))
            reward.name = "reward"
            tmp_train = pd.concat([tmp_train, reward], axis=1)
            reward_shift = tmp_train.groupby('id').apply(lambda x: x['reward'].shift(1)).fillna(0)
            
            lg_rewards.append(reward_shift)
            del y_pred, tmp_train, reward
            gc.collect()
            

LG_to_keep=3
targetselector=np.array(lg_rewards).T
targetselector=np.argmax(targetselector, axis=1)
print("selecting best models:")
print(pd.Series(targetselector).value_counts().head(LG_to_keep))
tokeep=pd.Series(targetselector).value_counts().head(LG_to_keep).index

for elt in tokeep:
    tokeepmodels.append(lg_models[elt])
    tokeepcolumns.append(lg_columns[elt])
    tokeeprewards.append(lg_rewards[elt])

del lg_models
del lg_columns
del lg_rewards
gc.collect()



print("training trees")

ET_models=[]
ET_columns=[]
ET_rewards=[]

model = ensemble.ExtraTreesRegressor(n_estimators=40, max_depth=4, n_jobs=-1, random_state=rnd, verbose=0)
model.fit(trainer,train.y)
print(pd.DataFrame(model.feature_importances_,index=treecols).sort_values(by=[0]).tail(20))
for elt in model.estimators_:
    ET_models.append(elt)
    ET_columns.append(treecols)
    
    y_pred = pd.Series(elt.predict(trainer[treecols]), index=train.index, name="y_pred")
    tmp_train = pd.concat([train[['id', 'timestamp', 'y']], y_pred], axis=1)
    reward = tmp_train.timestamp.map(tmp_train.groupby('timestamp').apply(lambda x: get_reward(x['y'], x['y_pred'])))
    reward.name = "reward"
    tmp_train = pd.concat([tmp_train, reward], axis=1)
    reward_shift = tmp_train.groupby('id').apply(lambda x: x['reward'].shift(1)).fillna(0)
    
    ET_rewards.append(reward_shift)
    del y_pred, tmp_train, reward
    gc.collect()




ET_to_keep=5
targetselector=np.array(ET_rewards).T
targetselector=np.argmax(targetselector, axis=1)

print("selecting best models:")
print(pd.Series(targetselector).value_counts().head(ET_to_keep))
tokeep=pd.Series(targetselector).value_counts().head(ET_to_keep).index

for elt in tokeep:
    tokeepmodels.append(ET_models[elt])
    tokeepcolumns.append(ET_columns[elt])
    tokeeprewards.append(ET_rewards[elt])

del ET_models
del ET_columns
del ET_rewards
gc.collect()

targetselector=np.array(tokeeprewards).T
avg_rewards = pd.Series(targetselector.mean(axis=1), index=trainer.index, name="reward")

targetselector=np.argmax(targetselector, axis=1)
trainer = pd.concat([trainer, avg_rewards], axis=1)
last_reward = trainer[train.timestamp == max(train.timestamp)]['reward'].iloc[-1]

#with Timer("Training ET selection model "):
print("training selection model")
modelselector = ensemble.ExtraTreesClassifier(n_estimators=100, max_depth=4, n_jobs=-1, random_state=rnd, verbose=0)
modelselector.fit(trainer[ list(cols2fit) + ['reward']], targetselector)
print(pd.DataFrame(modelselector.feature_importances_,index= list(cols2fit) + ['reward']).sort_values(by=[0]).tail(20))


for modelp in tokeepmodels:
    print("")
    print(modelp)


lastvalues=train[train.timestamp==max(train.timestamp)][['id']+diff_cols].copy()

del trainer
del train
del tokeeprewards
gc.collect()

print("end of training, now predicting")
indice=0
countplus=0
rewards=[]
infoList = []


while True:
    infoDict = dict()
    indice+=1
    test = o.features
    test["nbnulls"]=test.isnull().sum(axis=1)
    if add_nas_ft:
        for elt in nas_cols:
            test[elt + '_na'] = pd.isnull(test[elt]).apply(lambda x: 1 if x else 0)
    test=test.fillna(d_mean)
    
    timestamp = o.features.timestamp[0]

    pred = o.target
    if add_diff_ft:
        #creating deltas from lastvalues
        indexcommun=list(set(lastvalues.id) & set(test.id))
        lastvalues=pd.concat([test[test.id.isin(indexcommun)]['id'],
            pd.DataFrame(test[diff_cols][test.id.isin(indexcommun)].values-lastvalues[diff_cols][lastvalues.id.isin(indexcommun)].values,
            columns=diff_cols, index=test[test.id.isin(indexcommun)].index)],
            axis=1)
        #adding them to test data    
        test=test.merge(right=lastvalues, how='left', on='id', suffixes=('','_d')).fillna(0)
        #storing new lastvalues
        lastvalues=test[['id']+diff_cols].copy()
        

    test=featureexpander.transform(test[cols])
    #prediction using modelselector and models list
    test['reward'] = last_reward

    selected_prediction = modelselector.predict_proba(test.loc[: , list(cols2fit) + ['reward']])
    
    for ind,elt in enumerate(tokeepmodels):
        pred['y']+=selected_prediction[:,ind]*elt.predict(test[tokeepcolumns[ind]])
    
    
    o, reward, done, info = env.step(pred)
    
    #infoDict['timestamp'] = timestamp
    #infoDict['reward'] = reward
    #infoDict['score'] = info['public_score']
    #infoList.append(infoDict)
    
    last_reward = reward
    rewards.append(reward)
    if reward>0:
        countplus+=1
    
    if indice%100==0:
        print(indice, countplus, reward, np.mean(rewards), info)
        
    if done:
        print(info["public_score"])
        break

#pd.DataFrame(infoList).to_csv("../CSV/new_new2.csv", index=False)