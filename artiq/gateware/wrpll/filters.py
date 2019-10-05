helper_xn1 = 0
helper_xn2 = 0
helper_yn0 = 0
helper_yn1 = 0
helper_yn2 = 0

previous_helper_tag = 0

main_xn1 = 0
main_xn2 = 0
main_yn0 = 0
main_yn1 = 0
main_yn2 = 0


def helper(helper_tag):
    global helper_xn1, helper_xn2, helper_yn0, \
        helper_yn1, helper_yn2, previous_helper_tag

    helper_xn0 = helper_tag - previous_helper_tag - 32768

    helper_yr = 4294967296

    helper_yn2 = helper_yn1
    helper_yn1 = helper_yn0
    helper_yn0 = (
                 ((284885689*((217319150*helper_xn0 >> 44) +
                              (-17591968725107*helper_xn1 >> 44))) >> 44) +
                 (-35184372088832*helper_yn1 >> 44) -
                 (17592186044416*helper_yn2 >> 44))

    helper_xn2 = helper_xn1
    helper_xn1 = helper_xn0

    previous_helper_tag = helper_tag

    helper_yn0 = min(helper_yn0, helper_yr)
    helper_yn0 = max(helper_yn0, 0 - helper_yr)

    return helper_yn0


def main(main_xn0):
    global main_xn1, main_xn2, main_yn0, main_yn1, main_yn2

    main_yr = 4294967296

    main_yn2 = main_yn1
    main_yn1 = main_yn0
    main_yn0 = (
               ((133450380908*(((35184372088832*main_xn0) >> 44) +
                ((17592186044417*main_xn1) >> 44))) >> 44) +
               ((29455872930889*main_yn1) >> 44) -
               ((12673794781453*main_yn2) >> 44))

    main_xn2 = main_xn1
    main_xn1 = main_xn0

    main_yn0 = min(main_yn0, main_yr)
    main_yn0 = max(main_yn0, 0 - main_yr)

    return main_yn0
