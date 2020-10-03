# -*- coding: utf-8 -*-

'''
Implementation of solving Rectangle-Intersection Problem according algorithm proposed in
paper titled "A Rectangle-Intersection Algorithm with Limited Resource Requirements".

https://ieeexplore.ieee.org/document/5578313

- Performance

O(nlog n + k) time and O(n) space, where k is the count of intersection pairs

- Input

The rectangle is represented by its corner points, (x0, y0, x1, y1)

- Output

The output is an Adjacent List of each rect, which could be used to initialize a GRAPH.

---
@created: 2020-09-30
@author: train8808@gmail.com

'''

# procedure report(S, n)
# 1 Let V be the list of x-coordinates of the 2n vertical edges in S sorted in non-decreasing order.
# 2 Let H be the list of n y-intervals corresponding to the bottom and top y-coordinates of each rectangle.
# 3 Sort the elements of H in non-decreasing order by their bottom y-coordinates.
# 4 Call procedure detect(V, H, 2n).


def solve_rects_intersection(V:list, num:int, index_groups:list):
    ''' divide and conque in x-direction.
        ---
        Args:
        - V: rectangle-related x-edges data, [(index, Rect, x), (...), ...]
        - num: count of V instances, equal to len(V)
        - index_groups: target adjacent list for connectivity between rects
        
        ```
        procedure detect(V, H, m):
        if m < 2 then return else
        - let V1 be the first ⌊m/2⌋ and let V2 be the rest of the vertical edges in V in the sorted order;
        - let S11 and S22 be the set of rectangles represented only in V1 and V2 but not spanning V2 and V1,
            respectively;
        - let S12 be the set of rectangles represented only in V1 and spanning V2; 
        - let S21 be the set of rectangles represented only in V2 and spanning V1
        - let H1 and H2 be the list of y-intervals corresponding to the elements of V1 and V2 respectively
        - stab(S12, S22); stab(S21, S11); stab(S12, S21)
        - detect(V1, H1, ⌊m/2⌋); detect(V2, H2, m − ⌊m/2⌋)
        ```
    '''
    if num < 2: return
    
    # start/end points of left/right intervals
    center_pos = int(num/2.0)
    X0, X, X1 = V[0][-1], V[center_pos-1][-1], V[-1][-1] 

    # split into two groups
    left = V[0:center_pos]
    right = V[center_pos:]

    # filter rects according to their position to each intervals
    S11 = list(filter( lambda item: item[1][2]<=X, left ))
    S12 = list(filter( lambda item: item[1][2]>=X1, left ))
    S22 = list(filter( lambda item: item[1][0]>X, right ))
    S21 = list(filter( lambda item: item[1][0]<=X0, right ))
    
    # intersection in x-direction is fullfilled, so check y-direction further
    stab(S12, S22, index_groups)
    stab(S21, S11, index_groups)
    stab(S12, S21, index_groups)

    # recursive process
    solve_rects_intersection(left,  center_pos,     index_groups)
    solve_rects_intersection(right, num-center_pos, index_groups)


def stab(S1:list, S2:list, index_groups:list):
    '''Check interval intersection in y-direction.

        ```
        procedure stab(A, B)
            i := 1; j := 1
            while i ≤ |A| and j ≤ |B|
              if ai.y0 < bj.y0 then
                k := j
                while k ≤ |B| and bk.y0 < ai.y1
                  reportPair(air, bks)
                  k := k + 1
                i := i + 1
              else
                k := i
                while k ≤ |A| and ak.y0 < bj.y1
                  reportPair(bjs, akr)
                  k := k + 1
                j := j + 1
        ```
    '''
    if not S1 or not S2: return

    # sort
    S1.sort(key=lambda item: item[1][1])
    S2.sort(key=lambda item: item[1][1])

    i, j = 0, 0
    while i<len(S1) and j<len(S2):
        m, a, _ = S1[i]
        n, b, _ = S2[j]
        if a[1] < b[1]:
            k = j
            while k<len(S2) and S2[k][1][1] < a[3]:
                report_pair(int(m/2), int(S2[k][0]/2), index_groups)
                k += 1
            i += 1
        else:
            k = i
            while k<len(S1) and S1[k][1][1] < b[3]:
                report_pair(int(S1[k][0]/2), int(n/2), index_groups)
                k += 1
            j += 1


def report_pair(i:int, j:int, index_groups:list):
    '''add pair (i,j) to adjacent list.'''
    index_groups[i].add(j)
    index_groups[j].add(i)