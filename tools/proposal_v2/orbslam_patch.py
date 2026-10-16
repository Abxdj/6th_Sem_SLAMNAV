#!/usr/bin/env python3
"""proposal-v2 changes to ~/ORB_SLAM3, as layered exact-match edit groups.

Usage: orbslam_patch.py <group> [--root DIR] [--check]
Groups, applied in this order (each one commit on ORB_SLAM3 branch proposal-v2):
  C1  keyframe registry in LoopClosing + redirect culled candidates to a live ancestor
  C2  lookup across every live map; route other-map candidates to the merge list
  C3  Tracking publishes [kf_id, stamp] on /orb_slam3/new_keyframe (incl. the two init KFs)
  C5  per-proposal outcome accounting ([PROP] / [PROP-STATS]) and loop/merge attribution
  S   ROS wrapper: /orb_slam3/new_session -> System::ChangeDataset(); save all maps with map ids
Every anchor must occur exactly once or the script aborts without writing anything.
"""
import sys, os

# ----------------------------------------------------------------------------- C1
C1 = {
'include/LoopClosing.h': [
("""    KeyFrame* GetKeyFrameById(long unsigned int id);
""", """    KeyFrame* GetKeyFrameById(long unsigned int id);

    // proposal-v2 C1: every keyframe LoopClosing has seen, so culled ids can be redirected
    std::unordered_map<long unsigned int, KeyFrame*> mmAllKFs;
    std::mutex mMutexAllKFs;
    bool IsKeyFrameLive(KeyFrame* pKF);
    KeyFrame* ResolveExternalCandidate(long unsigned int id, int &nHops, std::string &sWhy);
"""),
("""#include <deque>
""", """#include <deque>
#include <unordered_map>
#include <string>
"""),
],
'src/LoopClosing.cc': [
("""void LoopClosing::InsertKeyFrame(KeyFrame *pKF)
{
    unique_lock<mutex> lock(mMutexLoopQueue);
""", """void LoopClosing::InsertKeyFrame(KeyFrame *pKF)
{
    {
        unique_lock<mutex> lockReg(mMutexAllKFs);
        mmAllKFs[pKF->mnId] = pKF;
    }
    unique_lock<mutex> lock(mMutexLoopQueue);
"""),
("""void LoopClosing::SetTracker(Tracking *pTracker)
""", """// proposal-v2 C1: a keyframe is live if it is not bad and belongs to a live map of the Atlas.
// Culled keyframes are never freed (KeyFrame::SetBadFlag keeps the object and mpParent);
// keyframes of a reset map are not freed either (Map::clear deletes are commented out).
bool LoopClosing::IsKeyFrameLive(KeyFrame* pKF)
{
    if(!pKF || pKF->isBad())
        return false;
    Map* pMap = pKF->GetMap();
    if(!pMap || pMap->IsBad())
        return false;
    for(Map* pM : mpAtlas->GetAllMaps())
        if(pM == pMap)
            return pMap == mpAtlas->GetCurrentMap();   // C1: current map only (C2 lifts this)
    return false;
}

KeyFrame* LoopClosing::ResolveExternalCandidate(long unsigned int id, int &nHops, std::string &sWhy)
{
    nHops = 0;
    KeyFrame* pKF = nullptr;
    {
        unique_lock<mutex> lockReg(mMutexAllKFs);
        auto it = mmAllKFs.find(id);
        if(it != mmAllKFs.end())
            pKF = it->second;
    }
    if(!pKF)
    {
        sWhy = "not_found";
        return nullptr;
    }
    while(pKF && !IsKeyFrameLive(pKF) && nHops < 20)
    {
        pKF = pKF->GetParent();
        nHops++;
    }
    if(!pKF || !IsKeyFrameLive(pKF))
    {
        sWhy = pKF ? "redirect_cap" : "no_live_ancestor";
        return nullptr;
    }
    if(nHops > 0)
        cout << "[PROP] redirect " << id << "->" << pKF->mnId << " hops=" << nHops << endl;
    return pKF;
}

void LoopClosing::SetTracker(Tracking *pTracker)
"""),
("""                KeyFrame* pExtCand = GetKeyFrameById(matchId);
                if(!pExtCand || pExtCand == mpCurrentKF)
                    continue;
""", """                int nHops = 0;
                std::string sWhy;
                KeyFrame* pExtCand = ResolveExternalCandidate(matchId, nHops, sWhy);
                if(!pExtCand)
                {
                    cout << "[PROP] drop " << sWhy << " cand=" << matchId << " curKF=" << mpCurrentKF->mnId << endl;
                    continue;
                }
                if(pExtCand == mpCurrentKF)
                {
                    cout << "[PROP] drop self cand=" << matchId << endl;
                    continue;
                }
"""),
],
}

# ----------------------------------------------------------------------------- C2
C2 = {
'src/LoopClosing.cc': [
("""    for(Map* pM : mpAtlas->GetAllMaps())
        if(pM == pMap)
            return pMap == mpAtlas->GetCurrentMap();   // C1: current map only (C2 lifts this)
    return false;
""", """    for(Map* pM : mpAtlas->GetAllMaps())
        if(pM == pMap)
            return true;                               // C2: any live map of the Atlas
    return false;
"""),
("""                bool alreadyPresent = false;
                for(KeyFrame* pKF : vpLoopBowCand)
                    if(pKF == pExtCand) { alreadyPresent = true; break; }
                if(alreadyPresent)
                    continue;

                vpLoopBowCand.push_back(pExtCand);
""", """                // C2: same map -> loop list, other map -> merge list
                const bool bToMerge = pExtCand->GetMap() != mpCurrentKF->GetMap();
                vector<KeyFrame*> &vpTarget = bToMerge ? vpMergeBowCand : vpLoopBowCand;
                bool alreadyPresent = false;
                for(KeyFrame* pKF : vpLoopBowCand)
                    if(pKF == pExtCand) { alreadyPresent = true; break; }
                for(KeyFrame* pKF : vpMergeBowCand)
                    if(pKF == pExtCand) { alreadyPresent = true; break; }
                if(alreadyPresent)
                {
                    cout << "[PROP] drop dup_with_dbow2 cand=" << pExtCand->mnId << endl;
                    continue;
                }

                vpTarget.push_back(pExtCand);
                cout << "[PROP] to_" << (bToMerge ? "merge" : "loop") << "_list cand=" << pExtCand->mnId
                     << " (req " << matchId << ") curKF=" << mpCurrentKF->mnId << endl;
"""),
],
}

# ----------------------------------------------------------------------------- C3
C3 = {
'include/Tracking.h': [
("""#include <std_msgs/Int32.h>
""", """#include <std_msgs/Int32.h>
#include <std_msgs/Float64MultiArray.h>
"""),
("""    ros::Publisher mKFIdPublisher;
""", """    ros::Publisher mKFIdPublisher;
    ros::Publisher mKFPublisher;          // proposal-v2 C3: [kf_id, stamp] on /orb_slam3/new_keyframe
    void PublishKeyFrame(KeyFrame* pKF);
"""),
],
'src/Tracking.cc': [
("""    mKFIdPublisher = nh.advertise<std_msgs::Int32>("/orb_slam3/new_keyframe_id", 10);
""", """    mKFIdPublisher = nh.advertise<std_msgs::Int32>("/orb_slam3/new_keyframe_id", 10);
    mKFPublisher = nh.advertise<std_msgs::Float64MultiArray>("/orb_slam3/new_keyframe", 100);
"""),
("""void Tracking::CreateNewKeyFrame()
{
""", """void Tracking::PublishKeyFrame(KeyFrame* pKF)
{
    if(!mbKFPublisherSet || !pKF)
        return;
    std_msgs::Int32 kfIdMsg;
    kfIdMsg.data = (int)pKF->mnId;
    mKFIdPublisher.publish(kfIdMsg);
    std_msgs::Float64MultiArray kfMsg;
    kfMsg.data = {(double)pKF->mnId, pKF->mTimeStamp};
    mKFPublisher.publish(kfMsg);
}

void Tracking::CreateNewKeyFrame()
{
"""),
("""    // --- Publish new keyframe ID for external loop closure descriptor nodes ---
    if(mbKFPublisherSet)
    {
        std_msgs::Int32 kfIdMsg;
        kfIdMsg.data = (int)pKF->mnId;
        mKFIdPublisher.publish(kfIdMsg);
    }
""", """    // --- Publish new keyframe ID (+ stamp) for external loop closure descriptor nodes ---
    PublishKeyFrame(pKF);
"""),
("""    mpLocalMapper->InsertKeyFrame(pKFini);
    mpLocalMapper->InsertKeyFrame(pKFcur);
""", """    mpLocalMapper->InsertKeyFrame(pKFini);
    mpLocalMapper->InsertKeyFrame(pKFcur);
    PublishKeyFrame(pKFini);   // proposal-v2 C3: the two init KFs were never published
    PublishKeyFrame(pKFcur);
"""),
],
}

# ----------------------------------------------------------------------------- C5
C5 = {
'include/LoopClosing.h': [
("""#include <unordered_map>
""", """#include <unordered_map>
#include <map>
#include <set>
#include <iomanip>
#include <algorithm>
"""),
("""    bool IsKeyFrameLive(KeyFrame* pKF);
""", """    bool IsKeyFrameLive(KeyFrame* pKF);

    // proposal-v2 C5: per-proposal outcome accounting and attribution
    std::map<std::string, int> mmPropCount;
    std::mutex mMutexProp;
    void PropCount(const std::string &k, int n = 1);
    void PrintPropStats(const char* tag);
    int mnPropPasses = 0;
    std::set<KeyFrame*> mspExtThisPass;       // our candidates injected in the current pass
    bool mbLastBoWHadBest = false;            // set by DetectCommonRegionsFromBoW
    bool mbLastBoWBestFromExt = false;
    long unsigned int mnLastBoWExtSrc = 0;
    bool mbLoopFromExt = false, mbMergeFromExt = false;   // attribution carried through temporal checks
    long unsigned int mnLoopExtSrc = 0, mnMergeExtSrc = 0;
"""),
],
'src/LoopClosing.cc': [
# counters + printer
("""bool LoopClosing::IsKeyFrameLive(KeyFrame* pKF)
""", """void LoopClosing::PropCount(const std::string &k, int n)
{
    unique_lock<mutex> lock(mMutexProp);
    mmPropCount[k] += n;
}

void LoopClosing::PrintPropStats(const char* tag)
{
    size_t q;
    { unique_lock<mutex> lq(mMutexExternalCand); q = mExternalCandQueue.size(); }   // never hold both locks
    unique_lock<mutex> lock(mMutexProp);
    cout << "[" << tag << "]";
    for(auto &kv : mmPropCount)
        cout << " " << kv.first << "=" << kv.second;
    cout << " queued=" << q << " pending_loop=" << (mbLoopFromExt ? 1 : 0)
         << " pending_merge=" << (mbMergeFromExt ? 1 : 0) << endl;
}

bool LoopClosing::IsKeyFrameLive(KeyFrame* pKF)
"""),
# received
("""    // bound the queue so a stalled consumer can't grow it without limit
    while(mExternalCandQueue.size() > 50)
        mExternalCandQueue.pop_front();
""", """    { unique_lock<mutex> lp(mMutexProp); mmPropCount["received"]++; }
    cout << "[PROP] received cur=" << msg->data[0] << " cand=" << msg->data[1] << endl;

    // bound the queue so a stalled consumer can't grow it without limit
    while(mExternalCandQueue.size() > 50)
    {
        { unique_lock<mutex> lp(mMutexProp); mmPropCount["drop_queue_cap"]++; }
        mExternalCandQueue.pop_front();
    }
"""),
# terminal drops in the drain
("""                    cout << "[PROP] drop " << sWhy << " cand=" << matchId << " curKF=" << mpCurrentKF->mnId << endl;
                    continue;
""", """                    cout << "[PROP] drop " << sWhy << " cand=" << matchId << " curKF=" << mpCurrentKF->mnId << endl;
                    PropCount("drop_" + sWhy);
                    continue;
"""),
("""                    cout << "[PROP] drop self cand=" << matchId << endl;
                    continue;
""", """                    cout << "[PROP] drop self cand=" << matchId << endl;
                    PropCount("drop_self");
                    continue;
"""),
("""                    cout << "[PROP] drop dup_with_dbow2 cand=" << pExtCand->mnId << endl;
                    continue;
""", """                    cout << "[PROP] drop dup_with_dbow2 cand=" << pExtCand->mnId << endl;
                    PropCount("drop_dup_with_dbow2");
                    continue;
                }
                if(mspExtThisPass.count(pExtCand))
                {
                    PropCount("drop_dup_in_queue");
                    continue;
"""),
("""                vpTarget.push_back(pExtCand);
""", """                vpTarget.push_back(pExtCand);
                mspExtThisPass.insert(pExtCand);
                if(nHops > 0) { PropCount("redirected"); PropCount("redirect_hops", nHops); }
                PropCount(bToMerge ? "to_merge_list" : "to_loop_list");
"""),
# reset per pass + DBoW2 candidate log (for T4)
("""        // --- External CNN/ViT loop closure candidate injection ---
        {
            unique_lock<mutex> lock(mMutexExternalCand);
""", """        // --- External CNN/ViT loop closure candidate injection ---
        mspExtThisPass.clear();
        {
            cout << "[DBOW] cur=" << mpCurrentKF->mnId << " t=" << std::setprecision(17) << mpCurrentKF->mTimeStamp
                 << std::setprecision(6) << " loop=";
            for(KeyFrame* k : vpLoopBowCand) cout << k->mnId << ",";
            cout << " merge=";
            for(KeyFrame* k : vpMergeBowCand) cout << k->mnId << ",";
            cout << endl;
        }
        {
            unique_lock<mutex> lock(mMutexExternalCand);
"""),
# lists not evaluated + attribution capture after evaluation
("""    //Loop candidates
    if(!bLoopDetectedInKF && !vpLoopBowCand.empty())
    {
        mbLoopDetected = DetectCommonRegionsFromBoW(vpLoopBowCand, mpLoopMatchedKF, mpLoopLastCurrentKF, mg2oLoopSlw, mnLoopNumCoincidences, mvpLoopMPs, mvpLoopMatchedMPs);
""", """    for(KeyFrame* pK : mspExtThisPass)
    {
        const bool bInMerge = std::find(vpMergeBowCand.begin(), vpMergeBowCand.end(), pK) != vpMergeBowCand.end();
        if((bInMerge && bMergeDetectedInKF) || (!bInMerge && bLoopDetectedInKF))
        {
            PropCount("not_evaluated");
            cout << "[PROP] not_evaluated cand=" << pK->mnId << endl;
        }
    }
    //Loop candidates
    if(!bLoopDetectedInKF && !vpLoopBowCand.empty())
    {
        mbLoopDetected = DetectCommonRegionsFromBoW(vpLoopBowCand, mpLoopMatchedKF, mpLoopLastCurrentKF, mg2oLoopSlw, mnLoopNumCoincidences, mvpLoopMPs, mvpLoopMatchedMPs);
        if(mbLastBoWHadBest)
        {
            if(mbLoopFromExt && !mbLastBoWBestFromExt) PropCount("unconfirmed_replaced_loop");
            mbLoopFromExt = mbLastBoWBestFromExt;
            mnLoopExtSrc = mnLastBoWExtSrc;
        }
"""),
("""        mbMergeDetected = DetectCommonRegionsFromBoW(vpMergeBowCand, mpMergeMatchedKF, mpMergeLastCurrentKF, mg2oMergeSlw, mnMergeNumCoincidences, mvpMergeMPs, mvpMergeMatchedMPs);
    }
""", """        mbMergeDetected = DetectCommonRegionsFromBoW(vpMergeBowCand, mpMergeMatchedKF, mpMergeLastCurrentKF, mg2oMergeSlw, mnMergeNumCoincidences, mvpMergeMPs, mvpMergeMatchedMPs);
        if(mbLastBoWHadBest)
        {
            if(mbMergeFromExt && !mbLastBoWBestFromExt) PropCount("unconfirmed_replaced_merge");
            mbMergeFromExt = mbLastBoWBestFromExt;
            mnMergeExtSrc = mnLastBoWExtSrc;
        }
    }
    if(!mspExtThisPass.empty() && (++mnPropPasses % 10 == 0))
        PrintPropStats("PROP-STATS");
"""),
# temporal-check give-ups: an attributed candidate that never got confirmed
("""            mnLoopNumNotFound++;
            if(mnLoopNumNotFound >= 2)
            {
""", """            mnLoopNumNotFound++;
            if(mnLoopNumNotFound >= 2)
            {
                if(mbLoopFromExt) { PropCount("unconfirmed_loop"); cout << "[PROP] unconfirmed list=loop src=" << mnLoopExtSrc << endl; }
                mbLoopFromExt = false;
"""),
("""            mnMergeNumNotFound++;
            if(mnMergeNumNotFound >= 2)
            {
""", """            mnMergeNumNotFound++;
            if(mnMergeNumNotFound >= 2)
            {
                if(mbMergeFromExt) { PropCount("unconfirmed_merge"); cout << "[PROP] unconfirmed list=merge src=" << mnMergeExtSrc << endl; }
                mbMergeFromExt = false;
"""),
# per-candidate stages inside DetectCommonRegionsFromBoW
("""    int index = 0;
    //Verbose::PrintMess("BoW candidates: There are " + to_string(vpBowCand.size()) + " possible candidates ", Verbose::VERBOSITY_DEBUG);
    for(KeyFrame* pKFi : vpBowCand)
    {
        if(!pKFi || pKFi->isBad())
            continue;
""", """    int index = 0;
    mbLastBoWHadBest = false; mbLastBoWBestFromExt = false; mnLastBoWExtSrc = 0;
    bool bBestFromExt = false; long unsigned int nBestExtSrc = 0;
    std::vector<long unsigned int> vExtGeomPass;
    //Verbose::PrintMess("BoW candidates: There are " + to_string(vpBowCand.size()) + " possible candidates ", Verbose::VERBOSITY_DEBUG);
    for(KeyFrame* pKFi : vpBowCand)
    {
        const bool bExt = mspExtThisPass.count(pKFi) > 0;
        int nExtStage = 0;   // 1 gate passed, 2 BoW matches, 3 Sim3 converged, 4 fully verified
        if(!pKFi || pKFi->isBad())
        {
            if(bExt) { PropCount("bad_at_eval"); }
            continue;
        }
"""),
("""        if(bAbortByNearKF)
        {
            mnAbortedByNearKF++;
""", """        if(bAbortByNearKF)
        {
            PropCount(bExt ? "abort_near" : "abort_near_dbow2");
            if(bExt) cout << "[PROP] abort_near cand=" << pKFi->mnId << " curKF=" << mpCurrentKF->mnId << endl;
            mnAbortedByNearKF++;
"""),
("""        if(numBoWMatches >= nBoWMatches) // TODO pick a good threshold
        {
""", """        nExtStage = 1;
        if(numBoWMatches >= nBoWMatches) // TODO pick a good threshold
        {
            nExtStage = 2;
"""),
("""            if(bConverge)
            {
""", """            if(bConverge)
            {
                nExtStage = 3;
"""),
("""                            if(nBestMatchesReproj < numProjOptMatches)
                            {
                                nBestMatchesReproj = numProjOptMatches;
""", """                            nExtStage = 4;
                            if(bExt) vExtGeomPass.push_back(pKFi->mnId);
                            if(nBestMatchesReproj < numProjOptMatches)
                            {
                                bBestFromExt = bExt;
                                nBestExtSrc = bExt ? pKFi->mnId : 0;
                                nBestMatchesReproj = numProjOptMatches;
"""),
("""        index++;
    }

    if(nBestMatchesReproj > 0)
    {
""", """        if(bExt && nExtStage < 4)
        {
            PropCount(nExtStage <= 1 ? "bow_fail" : "sim3_fail");
            cout << "[PROP] " << (nExtStage <= 1 ? "bow_fail" : "sim3_fail") << " cand=" << pKFi->mnId
                 << " stage=" << nExtStage << " bow=" << numBoWMatches << " curKF=" << mpCurrentKF->mnId << endl;
        }
        index++;
    }

    for(long unsigned int id : vExtGeomPass)
    {
        const bool bWon = bBestFromExt && id == nBestExtSrc;
        PropCount(bWon ? "geom_pass_best" : "geom_pass_not_best");
        cout << "[PROP] geom_pass cand=" << id << " best=" << bWon << " curKF=" << mpCurrentKF->mnId << endl;
    }
    if(nBestMatchesReproj > 0)
    {
        mbLastBoWHadBest = true;
        mbLastBoWBestFromExt = bBestFromExt;
        mnLastBoWExtSrc = nBestExtSrc;
"""),
# acceptance points
("""void LoopClosing::CorrectLoop()
{
    mnCorrectLoopCalls++;
""", """void LoopClosing::CorrectLoop()
{
    mnCorrectLoopCalls++;
    PropCount(mbLoopFromExt ? "accepted_loop" : "accepted_loop_dbow2");
    cout << "[PROP] accepted list=loop src=" << (mbLoopFromExt ? "ext" : "dbow2") << " ext_cand=" << mnLoopExtSrc
         << " matchedKF=" << mpLoopMatchedKF->mnId << " curKF=" << mpCurrentKF->mnId
         << " t=" << std::setprecision(17) << mpCurrentKF->mTimeStamp << std::setprecision(6) << endl;
    mbLoopFromExt = false;
"""),
("""void LoopClosing::SetFinish()
{
""", """void LoopClosing::SetFinish()
{
    PrintPropStats("PROP-FINAL");
"""),
],
}

S = {
'Examples_old/ROS/ORB_SLAM3/src/ros_mono.cc': [
("""#include <sensor_msgs/image_encodings.h>
""", """#include <sensor_msgs/image_encodings.h>
#include <std_msgs/Empty.h>
"""),
("""    ORB_SLAM3::System* mpSLAM;
};
""", """    ORB_SLAM3::System* mpSLAM;

    // proposal-v2 S: multi-session trigger, mirrors Examples/Monocular/mono_euroc.cc:182
    void NewSession(const std_msgs::EmptyConstPtr&)
    {
        cout << "[SESSION] ChangeDataset requested" << endl;
        mpSLAM->ChangeDataset();
    }
};
"""),
("""    ros::spin();

    // Stop all threads
""", """    ros::Subscriber subSession = nodeHandler.subscribe("/orb_slam3/new_session", 1, &ImageGrabber::NewSession, &igb);
    ros::spin();

    // Stop all threads
"""),
("""    SLAM.SaveKeyFrameTrajectoryTUM("KeyFrameTrajectory.txt");
""", """    SLAM.SaveKeyFrameTrajectoryTUM("KeyFrameTrajectory.txt");
    SLAM.SaveKeyFrameTrajectoryAllMapsTUM("KeyFrameTrajectory_allmaps.txt");
"""),
],
'include/System.h': [
("""    void SaveKeyFrameTrajectoryTUM(const string &filename);
""", """    void SaveKeyFrameTrajectoryTUM(const string &filename);
    // proposal-v2 S: every live map, one line per KF: map_id t x y z qx qy qz qw
    void SaveKeyFrameTrajectoryAllMapsTUM(const string &filename);
"""),
],
'src/System.cc': [
("""void System::SaveKeyFrameTrajectoryTUM(const string &filename)
{
""", """void System::SaveKeyFrameTrajectoryAllMapsTUM(const string &filename)
{
    cout << endl << "Saving all-maps keyframe trajectory to " << filename << " ..." << endl;
    ofstream f;
    f.open(filename.c_str());
    f << fixed;
    for(Map* pMap : mpAtlas->GetAllMaps())
    {
        if(!pMap || pMap->IsBad())
            continue;
        vector<KeyFrame*> vpKFs = pMap->GetAllKeyFrames();
        sort(vpKFs.begin(), vpKFs.end(), KeyFrame::lId);
        for(KeyFrame* pKF : vpKFs)
        {
            if(!pKF || pKF->isBad())
                continue;
            Sophus::SE3f Twc = pKF->GetPoseInverse();
            Eigen::Quaternionf q = Twc.unit_quaternion();
            Eigen::Vector3f t = Twc.translation();
            f << pMap->GetId() << " " << setprecision(6) << pKF->mTimeStamp << setprecision(7) << " " << t(0) << " " << t(1) << " " << t(2)
              << " " << q.x() << " " << q.y() << " " << q.z() << " " << q.w() << endl;
        }
    }
    f.close();
}

void System::SaveKeyFrameTrajectoryTUM(const string &filename)
{
"""),
],
}

# MergeLocal attribution (separate so the anchor is checked independently)
C5['src/LoopClosing.cc'].append(
("""void LoopClosing::MergeLocal()
{
""", """void LoopClosing::MergeLocal()
{
    PropCount(mbMergeFromExt ? "accepted_merge" : "accepted_merge_dbow2");
    cout << "[PROP] accepted list=merge src=" << (mbMergeFromExt ? "ext" : "dbow2") << " ext_cand=" << mnMergeExtSrc
         << " matchedKF=" << mpMergeMatchedKF->mnId << " curKF=" << mpCurrentKF->mnId
         << " t=" << std::setprecision(17) << mpCurrentKF->mTimeStamp << std::setprecision(6) << endl;
    mbMergeFromExt = false;
"""))

# C6 (cross-map proposer): the KF's map id at creation, so the node can restrict a query to other maps
C6 = {
'src/Tracking.cc': [
("""    kfMsg.data = {(double)pKF->mnId, pKF->mTimeStamp};
""", """    Map* pKFMap = pKF->GetMap();
    kfMsg.data = {(double)pKF->mnId, pKF->mTimeStamp, pKFMap ? (double)pKFMap->GetId() : -1.0};   // C6: + map id
"""),
],
}

GROUPS = {'C1': C1, 'C2': C2, 'C3': C3, 'C5': C5, 'S': S, 'C6': C6}

if __name__ == '__main__':
    g = sys.argv[1]
    root = os.path.expanduser(sys.argv[sys.argv.index('--root') + 1]) if '--root' in sys.argv else os.path.expanduser('~/ORB_SLAM3')
    check = '--check' in sys.argv
    new = {}
    for rel, edits in GROUPS[g].items():
        p = os.path.join(root, rel)
        s = new.get(p) or open(p).read()
        for old, rep in edits:
            n = s.count(old)
            if n != 1:
                sys.exit(f'ABORT {g} {rel}: anchor occurs {n} times: {old[:70]!r}')
            s = s.replace(old, rep)
        new[p] = s
    for p, s in new.items():
        if not check:
            open(p, 'w').write(s)
        print(('checked ' if check else 'patched ') + os.path.relpath(p, root))
