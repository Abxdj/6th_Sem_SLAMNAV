#!/usr/bin/env python3
"""Temporary H8 instrumentation for ~/ORB_SLAM3 (branch diag-counters). Prints only, prefixed [DIAG].
Every edit is an exact-match replacement that asserts a single occurrence.
Usage: h8_diag_patch.py apply|check
Backups of the pre-patch files are written next to this script's output dir by the caller."""
import sys, os
ROOT = os.path.expanduser('~/ORB_SLAM3')
EDITS = {
'include/LoopClosing.h': [
("""    int mnCorrectLoopCalls = 0;
""", """    int mnCorrectLoopCalls = 0;
    std::set<KeyFrame*> mspDiagInjected;   // [DIAG] temporary H8 instrumentation
"""),
],
'src/LoopClosing.cc': [
# A. receipt and cap drops
("""    unique_lock<mutex> lock(mMutexExternalCand);
    mExternalCandQueue.push_back(
        std::make_pair((long unsigned int)msg->data[0],
                       (long unsigned int)msg->data[1]));

    // bound the queue so a stalled consumer can't grow it without limit
    while(mExternalCandQueue.size() > 50)
        mExternalCandQueue.pop_front();
""", """    unique_lock<mutex> lock(mMutexExternalCand);
    mExternalCandQueue.push_back(
        std::make_pair((long unsigned int)msg->data[0],
                       (long unsigned int)msg->data[1]));
    cout << "[DIAG] recv cur=" << msg->data[0] << " cand=" << msg->data[1] << " q=" << mExternalCandQueue.size() << endl;

    // bound the queue so a stalled consumer can't grow it without limit
    while(mExternalCandQueue.size() > 50)
    {
        cout << "[DIAG] drop=cap cand=" << mExternalCandQueue.front().second << endl;
        mExternalCandQueue.pop_front();
    }
"""),
# E1. small-map early return
("""    if(mpLastMap->GetAllKeyFrames().size() < 12)
    {
""", """    if(mpLastMap->GetAllKeyFrames().size() < 12)
    {
        { unique_lock<mutex> lq(mMutexExternalCand); if(!mExternalCandQueue.empty()) cout << "[DIAG] skip=small_map q=" << mExternalCandQueue.size() << " curKF=" << mpCurrentKF->mnId << endl; }
"""),
# E2. temporal-confirmation early return
("""    if(mbMergeDetected || mbLoopDetected)
    {
#ifdef REGISTER_TIMES
        vdEstSim3_ms.push_back(timeEstSim3);
#endif
        mpKeyFrameDB->add(mpCurrentKF);
        return true;
    }
""", """    if(mbMergeDetected || mbLoopDetected)
    {
#ifdef REGISTER_TIMES
        vdEstSim3_ms.push_back(timeEstSim3);
#endif
        { unique_lock<mutex> lq(mMutexExternalCand); if(!mExternalCandQueue.empty()) cout << "[DIAG] skip=temporal_detected q=" << mExternalCandQueue.size() << " curKF=" << mpCurrentKF->mnId << endl; }
        mpKeyFrameDB->add(mpCurrentKF);
        return true;
    }
"""),
# B. drain outcomes
("""                KeyFrame* pExtCand = GetKeyFrameById(matchId);
                if(!pExtCand || pExtCand == mpCurrentKF)
                    continue;

                bool alreadyPresent = false;
                for(KeyFrame* pKF : vpLoopBowCand)
                    if(pKF == pExtCand) { alreadyPresent = true; break; }
                if(alreadyPresent)
                    continue;
""", """                KeyFrame* pExtCand = GetKeyFrameById(matchId);
                if(!pExtCand)
                {
                    std::string why = "culled";
                    for(Map* pM : mpAtlas->GetAllMaps())
                        for(KeyFrame* k : pM->GetAllKeyFrames())
                            if(k && k->mnId == matchId)
                                why = (pM == mpAtlas->GetCurrentMap()) ? "bad" : "other_map";
                    cout << "[DIAG] drop=" << why << " cand=" << matchId << " curKF=" << mpCurrentKF->mnId << endl;
                    continue;
                }
                if(pExtCand == mpCurrentKF)
                {
                    cout << "[DIAG] drop=self cand=" << matchId << endl;
                    continue;
                }

                bool alreadyPresent = false;
                for(KeyFrame* pKF : vpLoopBowCand)
                    if(pKF == pExtCand) { alreadyPresent = true; break; }
                if(alreadyPresent)
                {
                    cout << "[DIAG] drop=dup_bow cand=" << matchId << endl;
                    continue;
                }
                mspDiagInjected.insert(pExtCand);
"""),
# reset the injected set per pass
("""        // --- External CNN/ViT loop closure candidate injection ---
        {
            unique_lock<mutex> lock(mMutexExternalCand);
""", """        // --- External CNN/ViT loop closure candidate injection ---
        mspDiagInjected.clear();
        {
            unique_lock<mutex> lock(mMutexExternalCand);
"""),
# C. injected but loop list not evaluated
("""    //Loop candidates
    if(!bLoopDetectedInKF && !vpLoopBowCand.empty())
    {
""", """    if(bInjectedThisPass && bLoopDetectedInKF)
        cout << "[DIAG] drop=not_evaluated n=" << mspDiagInjected.size() << endl;
    //Loop candidates
    if(!bLoopDetectedInKF && !vpLoopBowCand.empty())
    {
"""),
# E3. no BoW query at all this pass
("""    if(!bMergeDetectedInKF || !bLoopDetectedInKF)
    {
        // Search in BoW
""", """    if(bMergeDetectedInKF && bLoopDetectedInKF)
    { unique_lock<mutex> lq(mMutexExternalCand); if(!mExternalCandQueue.empty()) cout << "[DIAG] skip=both_detected q=" << mExternalCandQueue.size() << endl; }
    if(!bMergeDetectedInKF || !bLoopDetectedInKF)
    {
        // Search in BoW
"""),
# D. gate outcome per origin
("""        if(bAbortByNearKF)
        {
            mnAbortedByNearKF++;
""", """        if(mspDiagInjected.count(pKFi))
            cout << "[DIAG] gate ext=" << pKFi->mnId << " abort=" << bAbortByNearKF << endl;
        if(bAbortByNearKF)
        {
            mnAbortedByNearKF++;
"""),
# F. leftovers at shutdown
("""void LoopClosing::SetFinish()
{
""", """void LoopClosing::SetFinish()
{
    cout << "[DIAG] queue_left=" << mExternalCandQueue.size() << endl;
"""),
],
}

mode = sys.argv[1]
for rel, edits in EDITS.items():
    p = os.path.join(ROOT, rel); s = open(p).read()
    for old, new in edits:
        n = s.count(old)
        assert n == 1, f'{rel}: expected 1 occurrence, found {n}: {old[:60]!r}'
        s = s.replace(old, new)
    if mode == 'apply':
        open(p, 'w').write(s)
    print(rel, 'ok', len(edits), 'edits', '(applied)' if mode == 'apply' else '(check only)')
