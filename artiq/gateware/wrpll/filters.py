import random as rand

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


def filter_helper(helper_tag):
    global helper_xn1, helper_xn2, helper_yn0, \
        helper_yn1, helper_yn2, previous_helper_tag

    helper_xn0 = helper_tag - previous_helper_tag - 1 << 15
    # This 1 << 15 is not an operation for filter. It is a constant.
    # However, different loop may use 1 << 14 or 1 << 15.

    helper_yr = 4294967296

    helper_yn2 = helper_yn1
    helper_yn1 = helper_yn0
    helper_yn0 = (
                 ((284885689*((217319150*helper_xn0 >> 44) +
                              (-17591968725107*helper_xn1 >> 44))) >> (44)) +
                 (-35184372088832*helper_yn1 >> 44) -
                 (17592186044416*helper_yn2 >> 44))
    # There is a 44 with (). All the other 44 will be a same constant value.
    # But the () one can be different constant than others

    helper_xn2 = helper_xn1
    helper_xn1 = helper_xn0

    previous_helper_tag = helper_tag

    helper_yn0 = min(helper_yn0, helper_yr)
    helper_yn0 = max(helper_yn0, - helper_yr)

    return helper_yn0


def main_filter(main_xn0):

    global main_xn1, main_xn2, main_yn0, main_yn1, main_yn2

    main_yr = 4294967296

    main_yn2 = main_yn1
    main_yn1 = main_yn0
    main_yn0 = (
               ((133450380908*(((35184372088832*main_xn0) >> 44) +
                ((17592186044417*main_xn1) >> 44))) >> (44)) +
               ((29455872930889*main_yn1) >> 44) -
               ((12673794781453*main_yn2) >> 44))
    # There is a 44 with (). All the other 44 will be a same constant value.
    # But the () one can be different constant than others

    main_xn2 = main_xn1
    main_xn1 = main_xn0

    main_yn0 = min(main_yn0, main_yr)
    main_yn0 = max(main_yn0, - main_yr)

    return main_yn0


def main():
    i = 0
    helper_data = []
    main_data = []
    while 1:
        helper_data.append(filter_helper(rand.randint(-128, 128)+i*32768))
        print(i, helper_data[i])
        main_data.append(main_filter(rand.randint(-128, 128)))
        print(i, main_data[i])
        i = i+1

if __name__ == '__main__':
    main()
