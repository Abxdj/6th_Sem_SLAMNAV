// Offline DBoW2 raw place-recognition scores, exactly as ORB-SLAM3 computes them for a keyframe:
// CLAHE(2.0, 8x8) as ros_nodes/clahe_node.py -> resize to Camera.newWidth x newHeight (EuRoC.yaml 600x350,
// System::TrackMonocular) -> ORBextractor(1000, 1.2, 8, 20, 7) -> ORBVocabulary::transform(desc, bow, feat, 4)
// -> ORBVocabulary::score(bow_q, bow_db) (the score DetectNBestCandidates accumulates).
// No covisibility exclusion, no group accumulation: raw per-keyframe score.
//
// Usage: dbow_query <ORBvoc.txt> <list.txt> <out.bin> [newW newH nFeatures]
//   list.txt lines: <session 0|1> <image_path>     (one line per keyframe, any order)
//   out.bin: int32 n0, int32 n1, then float32 [n1 x n0] = score(session-1 KF i, session-0 KF j), in list order.
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <opencv2/opencv.hpp>
#include "ORBextractor.h"
#include "ORBVocabulary.h"

using namespace std;

static vector<cv::Mat> rows(const cv::Mat &D)
{
    vector<cv::Mat> v;
    v.reserve(D.rows);
    for (int j = 0; j < D.rows; j++) v.push_back(D.row(j));
    return v;
}

int main(int argc, char **argv)
{
    if (argc < 4) { cerr << "usage: dbow_query voc list out [W H nFeat]" << endl; return 1; }
    const int W = argc > 4 ? atoi(argv[4]) : 600, H = argc > 5 ? atoi(argv[5]) : 350;
    const int NF = argc > 6 ? atoi(argv[6]) : 1000;
    ORB_SLAM3::ORBVocabulary voc;
    if (!voc.loadFromTextFile(argv[1])) { cerr << "vocabulary load failed" << endl; return 1; }
    ORB_SLAM3::ORBextractor ext(NF, 1.2f, 8, 20, 7);
    cv::Ptr<cv::CLAHE> clahe = cv::createCLAHE(2.0, cv::Size(8, 8));
    vector<DBoW2::BowVector> bow[2];
    ifstream in(argv[2]);
    int s; string path; long n = 0;
    while (in >> s >> path)
    {
        cv::Mat im = cv::imread(path, cv::IMREAD_GRAYSCALE);
        if (im.empty()) { cerr << "cannot read " << path << endl; return 1; }
        cv::Mat eq, rs;
        clahe->apply(im, eq);
        if (W > 0 && (eq.cols != W || eq.rows != H)) cv::resize(eq, rs, cv::Size(W, H)); else rs = eq;
        vector<cv::KeyPoint> kps; cv::Mat desc; vector<int> lap = {0, 1000};
        ext(rs, cv::Mat(), kps, desc, lap);
        DBoW2::BowVector bv; DBoW2::FeatureVector fv;
        voc.transform(rows(desc), bv, fv, 4);
        bow[s].push_back(bv);
        if (++n % 200 == 0) cerr << n << " images" << endl;
    }
    const int n0 = bow[0].size(), n1 = bow[1].size();
    ofstream out(argv[3], ios::binary);
    out.write((const char *)&n0, 4); out.write((const char *)&n1, 4);
    for (int i = 0; i < n1; i++)
        for (int j = 0; j < n0; j++)
        {
            float sc = (float)voc.score(bow[1][i], bow[0][j]);
            out.write((const char *)&sc, 4);
        }
    cerr << "wrote " << n1 << " x " << n0 << endl;
    return 0;
}
