import pandas as pd, numpy as np, scipy.stats as st, sys
df=pd.read_excel(sys.argv[1],sheet_name='DATA ENTRY')
df.columns=['id','group','item','made','Q1','Q2','Q3','tasted','Q4','Q5','Q6','time']
df['made']=df.made.str.strip().str.title(); df['tasted']=df.tasted.str.strip().str.title()
df.to_csv('candy_clean.csv',index=False)
print(df.group.value_counts().to_dict(), df.made.unique(), df.tasted.unique())
for v in ['Q1','Q2','Q3','Q4','Q5','Q6','time']:
    a=df[df.group=='A'][v].dropna(); b=df[df.group=='B'][v].dropna()
    sw=[st.shapiro(x).pvalue for x in (a,b)]; lv=st.levene(a,b,center='mean').pvalue
    t=st.ttest_ind(a,b); w=st.ttest_ind(a,b,equal_var=False); mw=st.mannwhitneyu(a,b,alternative='two-sided')
    sp=np.sqrt(((len(a)-1)*a.var()+(len(b)-1)*b.var())/(len(a)+len(b)-2)); d=(a.mean()-b.mean())/sp
    rbc=1-2*mw.statistic/(len(a)*len(b))
    print(f"{v}: A n={len(a)} M={a.mean():.3f} SD={a.std():.3f} | B n={len(b)} M={b.mean():.3f} SD={b.std():.3f} | SW A p={sw[0]:.3f} B p={sw[1]:.3f} | Levene p={lv:.3f} | t({len(a)+len(b)-2})={t.statistic:.3f} p={t.pvalue:.3f} d={d:.3f} | Welch t({w.df:.2f})={w.statistic:.3f} p={w.pvalue:.3f} | MW U={mw.statistic:.1f} p={mw.pvalue:.3f} rrb={-rbc:.3f}")
